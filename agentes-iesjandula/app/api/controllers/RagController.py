from fastapi import HTTPException, UploadFile
from app.api.services.RagService import rag_service

class RagController:
    @staticmethod
    async def upload_document(perfil: str, file: UploadFile):
        if not rag_service.validar_perfil(perfil):
            raise HTTPException(status_code=400, detail="Perfil no válido.")
        
        try:
            return await rag_service.procesar_subida(perfil, file)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def list_documents(perfil: str):
        if not rag_service.validar_perfil(perfil):
            raise HTTPException(status_code=400, detail="Perfil no válido.")
        return rag_service.listar_docs(perfil)

    @staticmethod
    async def delete_document(perfil: str, nombre_archivo: str):
        if not rag_service.validar_perfil(perfil):
            raise HTTPException(status_code=400, detail="Perfil no válido.")
            
        resultado = rag_service.eliminar_doc(perfil, nombre_archivo)
        if resultado["status"] == "error":
            raise HTTPException(status_code=404, detail=resultado["message"])
            
        return resultado