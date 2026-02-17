import os
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

current_dir = os.path.dirname(os.path.abspath(__file__))
pdf_path = os.path.join(current_dir, "guia-profesorado.pdf")
persist_db_path = os.path.join(current_dir, "chroma_db")

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

vector_store = Chroma(
    collection_name="guia_profesorado",
    embedding_function=embeddings,
    persist_directory=persist_db_path
)

def inicializar_base_datos():
    """
    Función para indexar el PDF solo si la base de datos está vacía.
    Se llamará desde el arranque de la aplicación.
    """
    num_docs_actuales = vector_store._collection.count()
    
    if num_docs_actuales == 0:
        if not os.path.exists(pdf_path):
            print(f"⚠️ Error: No se encontró el archivo PDF en {pdf_path}")
            return

        print("La base de datos está vacía. Indexando documentos...")
        loader = PyPDFLoader(pdf_path)
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=600,
            chunk_overlap=100
        )
        docs = loader.load_and_split(text_splitter)
        vector_store.add_documents(documents=docs)
        print(f"¡Indexación completada! ({len(docs)} fragmentos)")
    else:
        print(f"La base de datos ya contiene {num_docs_actuales} documentos. Lista para usar.")

# Si ejecutas este archivo directamente, se inicializa (para pruebas)
if __name__ == "__main__":
    inicializar_base_datos()