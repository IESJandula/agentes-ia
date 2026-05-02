import gc
import os
import uuid

from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
from pypdf import PdfReader
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions

load_dotenv()

# ---------------------------------------------------------------------------
# Configuración global
# ---------------------------------------------------------------------------

current_dir = os.path.dirname(os.path.abspath(__file__))
persist_db_path = os.path.join(current_dir, "chroma_db_v3")
RUTA_PDF_DEFAULT = os.path.join(current_dir, "guia-profesorado.pdf")

# Cliente ChromaDB persistente (singleton de módulo)
#client = chromadb.PersistentClient(path=persist_db_path)

chroma_host = os.getenv("CHROMA_SERVER_HOST", "localhost")
chroma_port = os.getenv("CHROMA_SERVER_HTTP_PORT", "8000")

client = chromadb.HttpClient(host=chroma_host, port=chroma_port)

# Función de embedding compartida (permite configurar URL por entorno para Docker)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

embedding_fn = OllamaEmbeddingFunction(
    model_name="qwen3-embedding:4b",
    url=OLLAMA_URL,
)

# Conversor Docling (singleton de módulo)
# Pipeline optimizada: desactiva generación de imágenes para reducir consumo de RAM
_pdf_pipeline_options = PdfPipelineOptions(
    do_table_structure=True,
    do_ocr=True,
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
DOCLING_PAGE_BATCH_SIZE = 8

# Colecciones — se crean si no existen
# Nombres internos de ChromaDB
_COLECCION_PROFESORES = "guia_profesorado"
_COLECCION_ALUMNOS    = "guia_alumnado"

# Perfil → nombre de colección ChromaDB
_PERFIL_A_COLECCION = {
    "profesores": _COLECCION_PROFESORES,
    "alumnos":    _COLECCION_ALUMNOS,
}

profesores_col = client.get_or_create_collection(
    name=_COLECCION_PROFESORES,
    embedding_function=embedding_fn,
)
alumnos_col = client.get_or_create_collection(
    name=_COLECCION_ALUMNOS,
    embedding_function=embedding_fn,
)

# Debug: Mostrar conteo al iniciar
print(f"📊 [DATABASE] Versión: {os.path.basename(persist_db_path)}")
print(f"📊 [DATABASE] Documentos en Profesores: {profesores_col.count()}")
print(f"📊 [DATABASE] Documentos en Alumnos:    {alumnos_col.count()}")

# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

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
            result = converter.convert(file_path, page_range=(start, end))
            texto_lote = result.document.export_to_markdown()
            if texto_lote and texto_lote.strip():
                partes_md.append(texto_lote)
                lotes_ok += 1
                print("✅")
            else:
                lotes_fail += 1
                print("⚠️ vacío")
        except Exception as e:
            lotes_fail += 1
            print(f"❌ {e}")
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
    chunks = text_splitter.split_text(texto)
    print(f"   {len(chunks)} fragmentos generados.")

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
    total = len(chunks)
    print(f"📤 [DEBUG] Subiendo {total} fragmentos en lotes de {BATCH_SIZE}...")
    try:
        for i in range(0, total, BATCH_SIZE):
            batch_docs  = documents[i:i+BATCH_SIZE]
            batch_meta  = metadatas[i:i+BATCH_SIZE]
            batch_ids   = ids[i:i+BATCH_SIZE]
            coleccion.add(
                documents=batch_docs,
                metadatas=batch_meta,
                ids=batch_ids,
            )
            print(f"   ✅ Lote {i//BATCH_SIZE + 1}/{-(-total//BATCH_SIZE)} insertado ({len(batch_docs)} chunks)")
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
            continue

        try:
            num_elementos = col.count()
            if num_elementos == 0:
                print(f"🆕 {label} vacía. Procesando...")
                n = procesar_y_añadir(path, perfil)
                print(f"✅ {label} inicializada con {n} fragmentos.")
            else:
                print(f"ℹ️ {label} ya tiene {num_elementos} fragmentos. Saltando.")
        except Exception as e:
            print(f"❌ ERROR inicializando {label}: {e}")