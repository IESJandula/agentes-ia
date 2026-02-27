from fastapi import APIRouter, UploadFile, File, HTTPException
from data.data import obtener_vector_store
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

router = APIRouter(prefix="/rag", tags=["RAG"])
text_splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=100)

@router.post("/upload/{perfil}")
async def subir_documento(perfil: str, file: UploadFile = File(...)):
    if perfil not in ["profesores", "alumnos"]:
        raise HTTPException(status_code=400, detail="Perfil no válido. Use 'profesores' o 'alumnos'.")

    v_store = obtener_vector_store(perfil)

    
    return {"status": "ok", "coleccion": f"guia_{perfil}"}