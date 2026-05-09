import chromadb
import os
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from dotenv import load_dotenv

load_dotenv()

# Esto es para debugging local
# En producción, usa el cliente HTTP de Coolify configurado en data.py

current_dir = os.path.dirname(os.path.abspath(__file__))
persist_db_path = os.path.join(current_dir, "chroma_db_v3")

client = chromadb.PersistentClient(path=persist_db_path)
embedding_fn = GoogleGenerativeAIEmbeddings(
    model="models/embedding-001",
    google_api_key=os.getenv("GENAI_API_KEY"),
)

prof_col = client.get_collection(name="guia_profesorado", embedding_function=embedding_fn)
alum_col = client.get_collection(name="guia_alumnado", embedding_function=embedding_fn)

print(f"--- DB INSPECTION (v3) ---")
print(f"Profesorado count: {prof_col.count()}")
print(f"Alumnado count:    {alum_col.count()}")

if prof_col.count() > 0:
    print("\nSample Prof Metadata:")
    print(prof_col.get(limit=1, include=["metadatas"]))
