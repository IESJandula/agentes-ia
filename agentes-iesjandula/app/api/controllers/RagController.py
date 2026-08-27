from fastapi import HTTPException, UploadFile
from typing import List
from app.api.services.RagService import rag_service
from app.api.services.KbService import kb_service

class RagController:
    @staticmethod
    async def upload_documents(perfil: str, files: List[UploadFile], usuario: str | None = None):
        if not rag_service.validar_perfil(perfil):
            raise HTTPException(status_code=400, detail="Perfil no válido.")

        try:
            return await rag_service.procesar_subida_multiple(perfil, files, usuario=usuario)
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

    # -- Gobierno de la base de conocimiento --------------------------------

    @staticmethod
    def kb_resumen():
        """Toda la base de conocimiento: categorías en orden y sus documentos."""
        return kb_service.resumen()

    @staticmethod
    def set_orden(orden: list[str]):
        """Cambia el orden en que se consultan las categorías."""
        try:
            nuevo = kb_service.set_orden(orden)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))

        # Los agentes cachean sus tools y su prompt al construirse: sin esto el
        # orden nuevo no se aplicaría hasta el próximo reinicio del contenedor.
        from app.api.services.AgenteService import agents_service
        agents_service.invalidar_agentes()

        return {"status": "ok", "orden": nuevo}

    @staticmethod
    def set_activo(perfil: str, nombre_archivo: str, activo: bool):
        """Retira (o vuelve a poner en juego) un documento sin borrarlo.

        Borrar un PDF de ChromaDB obliga a reindexarlo entero para recuperarlo,
        y con embeddings de cuota limitada eso no es gratis. Retirar es
        reversible y basta para sacar de las respuestas un documento caducado.
        """
        if not rag_service.validar_perfil(perfil):
            raise HTTPException(status_code=400, detail="Perfil no válido.")
        return kb_service.set_activo(perfil, nombre_archivo, activo)
