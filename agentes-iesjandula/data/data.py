import os
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader, UnstructuredMarkdownLoader
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

# Configuración de rutas y embeddings
current_dir = os.path.dirname(os.path.abspath(__file__))
persist_db_path = os.path.join(current_dir, "chroma_db")
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# Inicialización de colecciones (Chroma las crea si no existen)
def get_vector_store(collection_name):
    return Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=persist_db_path
    )

profesores_col = get_vector_store("guia_profesorado")
alumnos_col = get_vector_store("guia_alumnado")

# --- UTILIDADES ---

def obtener_loader(file_path):
    """Selecciona el loader adecuado según la extensión del archivo."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return PyPDFLoader(file_path)
    elif ext == ".md":
        return UnstructuredMarkdownLoader(file_path)
    elif ext == ".txt":
        return TextLoader(file_path, encoding="utf-8")
    else:
        raise ValueError(f"Formato no soportado: {ext}")

def procesar_y_añadir(file_path, target_collection):
    """Lógica común para fragmentar y subir documentos"""
    loader = obtener_loader(file_path)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=100)
    
    docs = loader.load_and_split(text_splitter)
    
    if target_collection == "profesores":
        profesores_col.add_documents(docs)
    else:
        alumnos_col.add_documents(docs)
    
    return len(docs)

# --- MÉTODOS PARA ENDPOINT ---

def inicializar_bases_datos(pdf_profes, pdf_alumnos):
    """Carga inicial de documentos base si las colecciones están vacías."""
    for col, path, name in [(profesores_col, pdf_profes, "Profesores"), 
                            (alumnos_col, pdf_alumnos, "Alumnos")]:
        if col._collection.count() == 0:
            if os.path.exists(path):
                num = procesar_y_añadir(path, name.lower())
                print(f"✅ {name} inicializado con {num} fragmentos.")
            else:
                print(f"⚠️ Archivo base para {name} no encontrado.")

def subir_nuevo_documento(file_path, perfil_seleccionado):
    """
    Este es el método que llamará tu API.
    perfil_seleccionado: 'profesores' o 'alumnos'
    """
    try:
        num_chunks = procesar_y_añadir(file_path, perfil_seleccionado)
        return {"status": "success", "chunks": num_chunks}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
def obtener_coleccion(perfil):
    """Helper para seleccionar la instancia de Chroma según el perfil."""
    return profesores_col if perfil == "profesores" else alumnos_col

def listar_documentos_en_coleccion(perfil):
    """
    Obtiene una lista de nombres de archivos únicos en la colección.
    """
    coleccion = obtener_coleccion(perfil)
    
    resultado = coleccion.get(include=['metadatas'])
    
    if not resultado['metadatas']:
        return []

    archivos = set()
    for meta in resultado['metadatas']:
        if meta and 'source' in meta:
            archivos.add(os.path.basename(meta['source']))
            
    return sorted(list(archivos))

def eliminar_documento_de_coleccion(perfil, nombre_archivo):
    """
    Elimina todos los fragmentos que pertenezcan a un archivo específico.
    """
    coleccion = obtener_coleccion(perfil)
    
    try:
        datos = coleccion.get()
        
       
        ids_a_borrar = [
            id_ for id_, meta in zip(datos['ids'], datos['metadatas'])
            if os.path.basename(meta.get('source', '')) == nombre_archivo
        ]

        if not ids_a_borrar:
            return {"status": "error", "message": f"No se encontró el archivo '{nombre_archivo}'"}


        coleccion.delete(ids=ids_a_borrar)
        
        return {
            "status": "success", 
            "message": f"Documento '{nombre_archivo}' eliminado correctamente",
            "chunks_eliminados": len(ids_a_borrar)
        }
            
    except Exception as e:
        return {"status": "error", "message": f"Error al eliminar: {str(e)}"}