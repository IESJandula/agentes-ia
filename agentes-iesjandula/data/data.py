import os
import uuid

from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
from docling.document_converter import DocumentConverter

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
converter = DocumentConverter()

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


def _extraer_texto(file_path: str) -> str:
    """
    Extrae el texto de un archivo.
    Intenta PyPDFLoader para PDFs; usa Docling como fallback o para imágenes.
    Devuelve el texto plano extraído.
    """
    ext = os.path.splitext(file_path)[1].lower()
    print(f"🔍 [DEBUG] Procesando: {file_path}  (ext: {ext})")

    if ext == ".pdf":
        try:
            print("--- [DEBUG] Intentando PyPDFLoader...")
            loader = PyPDFLoader(file_path)
            docs = loader.load()
            texto = "\n\n".join(d.page_content for d in docs)
            print(f"✅ [DEBUG] PyPDFLoader OK: {len(docs)} páginas.")
            return texto
        except Exception as e:
            print(f"⚠️ [DEBUG] PyPDFLoader falló ({e}). Usando Docling...")
            result = converter.convert(file_path)
            texto = result.document.export_to_markdown()
            print("✅ [DEBUG] Docling OK (fallback PDF).")
            return texto

    if ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp"):
        print("--- [DEBUG] Imagen → Docling OCR...")
        result = converter.convert(file_path)
        texto = result.document.export_to_markdown()
        print("✅ [DEBUG] Docling OCR OK.")
        return texto

    if ext in (".md", ".txt"):
        print(f"--- [DEBUG] Texto plano ({ext})...")
        with open(file_path, "r", encoding="utf-8") as f:
            texto = f.read()
        print("✅ [DEBUG] Texto cargado.")
        return texto

    # Formato desconocido → intentar Docling
    print(f"--- [DEBUG] Formato '{ext}' desconocido → Docling...")
    result = converter.convert(file_path)
    texto = result.document.export_to_markdown()
    print(f"✅ [DEBUG] Docling OK para '{ext}'.")
    return texto

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
        chunk_size=700,
        chunk_overlap=150,  # solapamiento aumentado para no perder contexto entre chunks
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
    en la colección del perfil indicado (extraídos del metadato 'source').
    """
    coleccion = obtener_coleccion(perfil)
    resultado = coleccion.get(include=["metadatas"])

    if not resultado["metadatas"]:
        return []

    archivos = {
        os.path.basename(meta["source"])
        for meta in resultado["metadatas"]
        if meta and "source" in meta
    }
    return sorted(archivos)


def eliminar_documento_de_coleccion(perfil: str, nombre_archivo: str) -> dict:
    """
    Elimina todos los chunks cuyo metadato 'source' coincida con 'nombre_archivo'.
    Devuelve {'status': 'success'|'error', 'message': str, 'chunks_eliminados': int}.
    """
    coleccion = obtener_coleccion(perfil)

    try:
        datos = coleccion.get(include=["metadatas"])

        ids_a_borrar = [
            id_
            for id_, meta in zip(datos["ids"], datos["metadatas"])
            if os.path.basename(meta.get("source", "")) == nombre_archivo
        ]

        if not ids_a_borrar:
            return {
                "status": "error",
                "message": f"No se encontró el archivo '{nombre_archivo}' en la colección '{perfil}'.",
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