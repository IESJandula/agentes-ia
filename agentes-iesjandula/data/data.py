import gc
import os
import time
import uuid

from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
import chromadb
from chromadb.api.types import EmbeddingFunction
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from pypdf import PdfReader
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions

load_dotenv()


class GeminiEmbeddingFunction(EmbeddingFunction):
    def __init__(self, api_key: str, model: str = "gemini-embedding-2"):
        self.api_key = api_key
        self.model = model
        self.embedding_client = GoogleGenerativeAIEmbeddings(
            model=self.model,
            api_key=self.api_key,
        )

    def __call__(self, input):
        if isinstance(input, str):
            input = [input]
        return self.embed_documents(list(input))

    def embed_documents(self, texts):
        """
        Genera embeddings para una lista de textos. 
        Asegura que la longitud de la salida coincida con la entrada.
        """
        try:
            embeddings = self.embedding_client.embed_documents(texts)
            if len(embeddings) != len(texts):
                print(f"⚠️ [EMBEDDINGS] Mismatch: {len(texts)} textos -> {len(embeddings)} vectores. Reintentando unitariamente...")
                # Si hay desajuste, procesar uno a uno para identificar el problema
                final_embeddings = []
                for t in texts:
                    try:
                        final_embeddings.append(self.embedding_client.embed_query(t))
                    except Exception as e:
                        print(f"❌ Error embebiendo texto individual: {e}")
                        # Vector de ceros como fallback si falla uno solo (dim 768 para text-embedding-004)
                        final_embeddings.append([0.0] * 768)
                return final_embeddings
            return embeddings
        except Exception as e:
            print(f"❌ Error crítico en embed_documents: {e}")
            raise

    def embed_query(self, text=None, *, input=None, **kwargs):
        # ChromaDB puede llamar embed_query(input=...) como kwarg
        query = text if text is not None else input
        return self.embedding_client.embed_query(query)

    @staticmethod
    def name() -> str:
        return "gemini-embeddings-v2"

    @staticmethod
    def build_from_config(config: dict) -> "GeminiEmbeddingFunction":
        return GeminiEmbeddingFunction(
            api_key=config["api_key"],
            model=config.get("model", "gemini-embedding-2"),
        )

    def get_config(self) -> dict:
        return {
            "api_key": self.api_key,
            "model": self.model,
        }

    def default_space(self):
        return "cosine"

    def supported_spaces(self):
        return ["cosine", "l2", "ip"]

# ---------------------------------------------------------------------------
# Configuración global
# ---------------------------------------------------------------------------

current_dir = os.path.dirname(os.path.abspath(__file__))
persist_db_path = os.path.join(current_dir, "chroma_db_v3")
RUTA_PDF_DEFAULT = os.path.join(current_dir, "guia-profesorado.pdf")

# Cliente ChromaDB persistente (singleton de módulo)
# Nota: por defecto el proyecto despliega Chroma localmente sin servicio HTTP externo.
chroma_host = os.getenv("CHROMA_SERVER_HOST", "localhost")
chroma_port = int(os.getenv("CHROMA_SERVER_HTTP_PORT", "8000"))
chroma_use_http = os.getenv("CHROMA_USE_HTTP", "false").strip().lower() in ("1", "true", "yes", "on")
chroma_persist_path = os.getenv("CHROMA_PERSIST_PATH", persist_db_path)

client = None
max_intentos_db = 5

if chroma_use_http:
    for i in range(max_intentos_db):
        try:
            print(f"📡 [DATABASE] Intentando conectar a ChromaDB en {chroma_host}:{chroma_port} (intento {i+1}/{max_intentos_db})...")
            client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
            # Probar conexión real
            client.heartbeat()
            print("✅ [DATABASE] Conexión HTTP a ChromaDB exitosa.")
            break
        except Exception as e:
            if i == max_intentos_db - 1:
                raise ConnectionError(
                    f"❌ No se pudo conectar al servidor Chroma en {chroma_host}:{chroma_port} tras {max_intentos_db} intentos. "
                    f"Error: {e}"
                )
            time.sleep(2)
else:
    os.makedirs(chroma_persist_path, exist_ok=True)
    print(f"📡 [DATABASE] Usando ChromaDB local persistente en {chroma_persist_path}")
    client = chromadb.PersistentClient(path=chroma_persist_path)
    print("✅ [DATABASE] ChromaDB local persistente inicializado.")

# Embeddings de Gemini: API nativa integrada en LangChain
# Requiere GENAI_API_KEY en variables de entorno
if not os.getenv("GOOGLE_API_KEY"):
    raise ValueError("⚠️ GOOGLE_API_KEY no está configurada en las variables de entorno")

embedding_fn = GeminiEmbeddingFunction(
    api_key=os.getenv("GOOGLE_API_KEY"),
    model="models/gemini-embedding-2",
)

# Conversor Docling (singleton de módulo)
# Pipeline optimizada: desactiva generación de imágenes para reducir consumo de RAM
_pdf_pipeline_options = PdfPipelineOptions(
    do_table_structure=True,
    do_ocr=False, # OCR DESACTIVADO: Evita el OOMKilled en servidores pequeños (reduce el uso de RAM de 3GB a ~200MB)
    generate_page_images=False,
    generate_picture_images=False,
    generate_table_images=False,
)
converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=_pdf_pipeline_options),
    }
)

# Número de páginas por lote para Docling (evita std::bad_alloc en PDFs grandes)
# Reducido a 4 para ser más conservador con la memoria
DOCLING_PAGE_BATCH_SIZE = 4

# Colecciones — se crean si no existen
# Nombres internos de ChromaDB
_COLECCION_PROFESORES = "guia_profesorado"
_COLECCION_ALUMNOS    = "guia_alumnado"

# Perfil → nombre de colección ChromaDB
_PERFIL_A_COLECCION = {
    "profesores": _COLECCION_PROFESORES,
    "alumnos":    _COLECCION_ALUMNOS,
}

def _crear_o_recrear_coleccion(nombre_coleccion: str, embedding_fn):
    """
    Crea o recrea una colección ChromaDB, manejando conflictos de función de embedding.
    Si hay conflicto (ej: colección con Ollama y queremos Gemini), elimina y recrea.
    """
    try:
        # Intentar crear/obtener la colección con la nueva función de embedding
        col = client.get_or_create_collection(
            name=nombre_coleccion,
            embedding_function=embedding_fn,
        )
        print(f"✅ [DATABASE] Colección '{nombre_coleccion}' lista.")
        return col
    except ValueError as e:
        if "embedding function already exists" in str(e).lower():
            print(f"⚠️ [DATABASE] Conflicto de función de embedding en '{nombre_coleccion}'. Eliminando y recreando...")
            try:
                client.delete_collection(nombre_coleccion)
                print(f"🗑️ [DATABASE] Colección '{nombre_coleccion}' eliminada.")
            except Exception as del_e:
                print(f"⚠️ [DATABASE] Error eliminando colección '{nombre_coleccion}': {del_e}")
            
            # Recrear con la nueva función de embedding
            col = client.get_or_create_collection(
                name=nombre_coleccion,
                embedding_function=embedding_fn,
            )
            print(f"✅ [DATABASE] Colección '{nombre_coleccion}' recreada con nueva función de embedding.")
            return col
        else:
            raise  # Re-lanzar si no es el error esperado

profesores_col = _crear_o_recrear_coleccion(_COLECCION_PROFESORES, embedding_fn)
alumnos_col = _crear_o_recrear_coleccion(_COLECCION_ALUMNOS, embedding_fn)

# Debug: Mostrar conteo al iniciar
print(f"📊 [DATABASE] Versión: {os.path.basename(persist_db_path)}")
print(f"📊 [DATABASE] Documentos en Profesores: {profesores_col.count()}")
print(f"📊 [DATABASE] Documentos en Alumnos:    {alumnos_col.count()}")

# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def query_coleccion(coleccion, query: str, n_results: int = 8, include=None):
    """
    Realiza una búsqueda semántica en una colección ChromaDB evitando el error
    'float object has no attribute tolist' que ocurre cuando ChromaDB intenta
    procesar internamente el resultado de GoogleGenerativeAIEmbeddings.

    Solución: calculamos el embedding nosotros y lo pasamos como query_embeddings
    (List[List[float]]) en lugar de usar query_texts (que delega en ChromaDB).
    """
    if include is None:
        include = ["documents", "metadatas", "distances"]

    # Calcular embedding manualmente → List[float]
    vector: list[float] = embedding_fn.embed_query(query)

    # ChromaDB espera query_embeddings: List[List[float]]
    return coleccion.query(
        query_embeddings=[vector],
        n_results=n_results,
        include=include,
    )


def obtener_coleccion(perfil: str):
    """
    Devuelve el objeto de colección ChromaDB según el perfil ('profesores'|'alumnos').
    Lanza ValueError si el perfil no es válido.
    """
    if perfil == "profesores":
        return profesores_col
    elif perfil == "alumnos":
        return alumnos_col
    raise ValueError(f"Perfil desconocido: '{perfil}'. Usa 'profesores' o 'alumnos'.")


def _contar_paginas_pdf(file_path: str) -> int:
    """Devuelve el número de páginas de un PDF usando pypdf."""
    try:
        reader = PdfReader(file_path)
        return len(reader.pages)
    except Exception as e:
        print(f"⚠️ [DEBUG] No se pudo contar páginas con pypdf: {e}")
        return 0


def _extraer_texto_docling_por_lotes(file_path: str, total_pages: int) -> str:
    """
    Procesa un PDF con Docling en lotes de DOCLING_PAGE_BATCH_SIZE páginas.
    Llama a gc.collect() entre lotes para liberar memoria y evitar std::bad_alloc.
    """
    batch = DOCLING_PAGE_BATCH_SIZE
    partes_md = []
    lotes_ok = 0
    lotes_fail = 0

    print(f"📄 [DEBUG] PDF con {total_pages} páginas → lotes de {batch}")

    for start in range(1, total_pages + 1, batch):
        end = min(start + batch - 1, total_pages)
        lote_num = (start // batch) + 1
        print(f"   📖 Lote {lote_num}: páginas {start}–{end} ...", end=" ")
        
        try:
            # Intentar procesar el lote completo
            result = converter.convert(file_path, page_range=(start, end))
            texto_lote = result.document.export_to_markdown()
            if texto_lote and texto_lote.strip():
                partes_md.append(texto_lote)
                lotes_ok += 1
                print("✅")
            else:
                print("⚠️ vacío")
        except Exception as e:
            # Si el lote falla (posible std::bad_alloc), reintentar página por página
            print(f"❌ Error en lote ({e}). Reintentando página a página...")
            for p in range(start, end + 1):
                print(f"      📄 Página {p} ...", end=" ")
                try:
                    res_p = converter.convert(file_path, page_range=(p, p))
                    txt_p = res_p.document.export_to_markdown()
                    if txt_p.strip():
                        partes_md.append(txt_p)
                        print("✅")
                    else:
                        print("⚠️ vacía")
                except Exception as ep:
                    print(f"❌ Fallo crítico: {ep}")
                    lotes_fail += 1
                finally:
                    gc.collect() # Limpiar después de cada página en modo fallback
        finally:
            # Liberar memoria entre lotes
            gc.collect()

    print(f"   📊 Resumen: {lotes_ok} lotes OK, {lotes_fail} lotes fallidos")
    return "\n\n".join(partes_md)


def _extraer_texto(file_path: str) -> str:
    """
    Extrae el texto de un archivo.
    Prioriza Docling para todos los formatos (PDF, imágenes, etc.) por su capacidad OCR y de estructura.
    Para PDFs, procesa en lotes de páginas para evitar errores de memoria (std::bad_alloc).
    Usa PyPDFLoader como fallback específico para PDFs si Docling falla.
    """
    ext = os.path.splitext(file_path)[1].lower()
    print(f"🔍 [DEBUG] Procesando: {file_path}  (ext: {ext})")

    # 1. Intentar con Docling (Prioridad máxima)
    try:
        print("--- [DEBUG] Intentando extracción con Docling...")

        if ext == ".pdf":
            # PDFs: procesar por lotes de páginas para evitar bad_alloc
            total_pages = _contar_paginas_pdf(file_path)
            if total_pages > 0:
                texto = _extraer_texto_docling_por_lotes(file_path, total_pages)
            else:
                # Si no pudimos contar páginas, intentar de golpe como último recurso
                print("   ⚠️ No se pudo contar páginas, intentando conversión completa...")
                result = converter.convert(file_path)
                texto = result.document.export_to_markdown()
        else:
            # No-PDF (imágenes, etc.): procesar de una vez
            result = converter.convert(file_path)
            texto = result.document.export_to_markdown()

        if texto and texto.strip():
            print("✅ [DEBUG] Extracción con Docling OK.")
            return texto
        print("⚠️ [DEBUG] Docling devolvió texto vacío.")
    except Exception as e:
        print(f"⚠️ [DEBUG] Docling falló: {e}")

    # 2. Fallback según extensión
    if ext == ".pdf":
        try:
            print("--- [DEBUG] Fallback: Intentando PyPDFLoader...")
            loader = PyPDFLoader(file_path)
            docs = loader.load()
            texto = "\n\n".join(d.page_content for d in docs)
            print(f"✅ [DEBUG] PyPDFLoader OK: {len(docs)} páginas.")
            return texto
        except Exception as e:
            print(f"❌ [DEBUG] Todos los extractores fallaron para PDF: {e}")

    if ext in (".md", ".txt"):
        try:
            print(f"--- [DEBUG] Fallback: Lectura de texto plano ({ext})...")
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"❌ [DEBUG] Error leyendo archivo de texto: {e}")

    return ""

# ---------------------------------------------------------------------------
# Lógica principal de procesamiento
# ---------------------------------------------------------------------------

def procesar_y_añadir(file_path: str, perfil: str, nombre_original: str = None) -> int:
    """
    Extrae, fragmenta e inserta el documento en la colección indicada por 'perfil'.
    Cada chunk se almacena como un documento independiente con metadatos completos.
    Devuelve el número de chunks insertados.
    """
    print(f"🚀 [DEBUG] Iniciando proceso — perfil: {perfil}, archivo: {file_path}")

    texto = _extraer_texto(file_path)

    if not texto or not texto.strip():
        print(f"⚠️ [DEBUG] Sin contenido extraído de {file_path}. Abortando.")
        return 0

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500,
        chunk_overlap=300,  # solapamiento aumentado para no perder contexto entre chunks
    )
    print("✂️ [DEBUG] Fragmentando texto...")
    raw_chunks = text_splitter.split_text(texto)
    # Filtramos fragmentos vacíos o que solo contengan espacios
    chunks = [c for c in raw_chunks if c.strip()]
    print(f"   {len(chunks)} fragmentos válidos generados (de {len(raw_chunks)} originales).")

    nombre_archivo = nombre_original if nombre_original else os.path.basename(file_path)
    nombre_coleccion = _PERFIL_A_COLECCION[perfil]

    documents = []
    metadatas = []
    ids = []

    for i, chunk_text in enumerate(chunks):
        chunk_id = str(uuid.uuid4())
        meta = {
            "source":        nombre_archivo,       # clave para listar/borrar por archivo
            "full_path":     file_path,
            "collection":    nombre_coleccion,
            "perfil":        perfil,
            "chunk_uuid":    chunk_id,
            "chunk_index":   i,
            "total_chunks":  len(chunks),
        }
        documents.append(chunk_text)
        metadatas.append(meta)
        ids.append(chunk_id)

    coleccion = obtener_coleccion(perfil)

    BATCH_SIZE = 20
    MAX_RETRIES = 3
    PAUSE_ENTRE_LOTES = 5   # segundos entre lotes para respetar rate-limit
    total = len(chunks)
    num_lotes = -(-total // BATCH_SIZE)
    print(f"📤 [DEBUG] Subiendo {total} fragmentos en {num_lotes} lotes de {BATCH_SIZE}...")
    print(f"   ⏱️  Pausa de {PAUSE_ENTRE_LOTES}s entre lotes (rate-limit: 100 req/min free tier)")
    try:
        for i in range(0, total, BATCH_SIZE):
            batch_docs  = documents[i:i+BATCH_SIZE]
            batch_meta  = metadatas[i:i+BATCH_SIZE]
            batch_ids   = ids[i:i+BATCH_SIZE]
            lote_actual = i // BATCH_SIZE + 1

            # Retry con backoff exponencial para manejar 429 RESOURCE_EXHAUSTED
            for intento in range(1, MAX_RETRIES + 1):
                try:
                    # Generar embeddings manualmente para mayor robustez
                    print(f"   🌀 Generando vectores para lote {lote_actual}...")
                    batch_embeddings = embedding_fn.embed_documents(batch_docs)
                    
                    if len(batch_embeddings) != len(batch_docs):
                        raise ValueError(f"Longitud inconsistente: {len(batch_docs)} docs vs {len(batch_embeddings)} embeddings")

                    coleccion.add(
                        documents=batch_docs,
                        metadatas=batch_meta,
                        ids=batch_ids,
                        embeddings=batch_embeddings
                    )
                    print(f"   ✅ Lote {lote_actual}/{num_lotes} insertado ({len(batch_docs)} chunks)")
                    break  # éxito, salir del bucle de reintentos
                except Exception as batch_err:
                    err_str = str(batch_err)
                    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                        wait_time = PAUSE_ENTRE_LOTES * (2 ** intento)  # backoff exponencial
                        print(f"   ⏳ Rate-limit (Gemini) en lote {lote_actual}, intento {intento}/{MAX_RETRIES}. "
                              f"Esperando {wait_time}s...")
                        time.sleep(wait_time)
                        if intento == MAX_RETRIES:
                            print(f"❌ [DEBUG] Lote {lote_actual} falló tras {MAX_RETRIES} reintentos.")
                            raise
                    else:
                        print(f"   ❌ Error en lote {lote_actual} (intento {intento}/{MAX_RETRIES}): {batch_err}")
                        if intento == MAX_RETRIES:
                            raise  # error no recuperable tras reintentos
                        time.sleep(2)

            # Pausa entre lotes para no superar el rate-limit
            if i + BATCH_SIZE < total:
                time.sleep(PAUSE_ENTRE_LOTES)
    except Exception as e:
        print(f"❌ [DEBUG] Error en la inserción: {e}")
        raise

    return total

# ---------------------------------------------------------------------------
# API pública — usada por RagService
# ---------------------------------------------------------------------------

def subir_nuevo_documento(file_path: str, perfil: str, nombre_original: str = None) -> dict:
    """
    Punto de entrada para subir un documento desde el endpoint de la API.
    Devuelve {'status': 'success'|'error', 'chunks': int, 'message': str}.
    """
    try:
        num_chunks = procesar_y_añadir(file_path, perfil, nombre_original)
        return {"status": "success", "chunks": num_chunks}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def listar_documentos_en_coleccion(perfil: str) -> list[str]:
    """
    Devuelve una lista ordenada de nombres de archivo únicos presentes
    en la colección del perfil indicado.
    """
    coleccion = obtener_coleccion(perfil)
    
    # Obtenemos TODOS los metadatos sin límite (limit=None o un número muy alto)
    # Algunas versiones de Chroma requieren un número explícito si no se quiere límite
    resultado = coleccion.get(include=["metadatas"])

    if not resultado or not resultado.get("metadatas"):
        return []

    archivos = set()
    for meta in resultado["metadatas"]:
        if meta and "source" in meta:
            # Normalizamos el nombre: solo el nombre del archivo, sin rutas
            nombre = os.path.basename(str(meta["source"]))
            if nombre:
                archivos.add(nombre)
    
    return sorted(list(archivos))


def eliminar_documento_de_coleccion(perfil: str, nombre_archivo: str) -> dict:
    """
    Elimina todos los chunks cuyo metadato 'source' coincida con 'nombre_archivo'.
    """
    coleccion = obtener_coleccion(perfil)

    try:
        # Obtenemos los IDs y metadatos para buscar la coincidencia
        datos = coleccion.get(include=["metadatas"])

        ids_a_borrar = []
        for id_, meta in zip(datos["ids"], datos["metadatas"]):
            if meta and "source" in meta:
                # Comparamos solo el nombre del archivo (ignorando rutas)
                if os.path.basename(str(meta["source"])) == nombre_archivo:
                    ids_a_borrar.append(id_)

        if not ids_a_borrar:
            return {
                "status": "error",
                "message": f"No se encontraron fragmentos para '{nombre_archivo}'.",
            }

        coleccion.delete(ids=ids_a_borrar)
        return {
            "status": "success",
            "message": f"'{nombre_archivo}' eliminado correctamente.",
            "chunks_eliminados": len(ids_a_borrar),
        }

    except Exception as e:
        return {"status": "error", "message": f"Error al eliminar: {str(e)}"}


# ---------------------------------------------------------------------------
# Inicialización al arrancar la app (opcional)
# ---------------------------------------------------------------------------

def inicializar_bases_datos(pdf_profes: str = None, pdf_alumnos: str = None):
    """
    Carga los PDFs de arranque si las colecciones están vacías.
    Si no se pasa pdf_alumnos, esa colección se ignora.
    """
    pdf_profes = pdf_profes or RUTA_PDF_DEFAULT

    configuracion = [
        (profesores_col, pdf_profes, "profesores", "Guía de Profesores"),
        (alumnos_col,    pdf_alumnos, "alumnos",    "Guía de Alumnos"),
    ]

    for col, path, perfil, label in configuracion:
        if not path:
            print(f"ℹ️ No se proporcionó ruta para {label}, ignorando.")
            continue

        if not os.path.exists(path):
            print(f"⚠️ Archivo no encontrado: {path}")
            # Debug: Listar archivos para ver qué hay realmente en el servidor
            try:
                folder = os.path.dirname(path)
                if os.path.exists(folder):
                    print(f"📂 Contenido de la carpeta {folder}: {os.listdir(folder)}")
                else:
                    print(f"❌ La carpeta contenedora no existe: {folder}")
            except Exception as e:
                print(f"⚠️ No se pudo listar la carpeta: {e}")
            continue

        try:
            num_elementos = col.count()

            # Detectar carga incompleta: buscar metadato "total_chunks" en el primer doc
            carga_completa = True
            if num_elementos > 0:
                muestra = col.get(limit=1, include=["metadatas"])
                if muestra and muestra.get("metadatas"):
                    total_esperado = muestra["metadatas"][0].get("total_chunks", num_elementos)
                    if num_elementos < total_esperado:
                        print(f"⚠️ {label} incompleta ({num_elementos}/{total_esperado} chunks). Reprocesando...")
                        client.delete_collection(col.name)
                        # Recrear la colección vacía
                        if perfil == "profesores":
                            globals()["profesores_col"] = client.get_or_create_collection(
                                name=col.name, embedding_function=embedding_fn
                            )
                            col = globals()["profesores_col"]
                        else:
                            globals()["alumnos_col"] = client.get_or_create_collection(
                                name=col.name, embedding_function=embedding_fn
                            )
                            col = globals()["alumnos_col"]
                        num_elementos = 0
                        carga_completa = False

            if num_elementos == 0:
                print(f"🆕 {label} vacía. Procesando...")
                n = procesar_y_añadir(path, perfil)
                print(f"✅ {label} inicializada con {n} fragmentos.")
            elif carga_completa:
                print(f"ℹ️ {label} ya tiene {num_elementos} fragmentos completos. Saltando.")
        except Exception as e:
            # Si falla durante la carga, borrar la colección parcial para permitir
            # un reintento limpio en el próximo arranque
            print(f"❌ ERROR inicializando {label}: {e}")
            try:
                client.delete_collection(col.name)
                print(f"🗑️ Colección parcial '{col.name}' borrada para reintento limpio.")
            except Exception:
                pass