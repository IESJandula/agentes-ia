from fastapi import APIRouter, UploadFile, File
from app.api.controllers.RagController import RagController

router = APIRouter(prefix="/rag", tags=["RAG"])

@router.post("/upload/{perfil}")
async def subir_documento(perfil: str, file: UploadFile = File(...)):
    return await RagController.upload_document(perfil, file)

@router.get("/documents/{perfil}")
async def listar_documentos(perfil: str):
    return await RagController.list_documents(perfil)

@router.delete("/documents/{perfil}/{nombre_archivo}")
async def borrar_documento(perfil: str, nombre_archivo: str):
    return await RagController.delete_document(perfil, nombre_archivo)