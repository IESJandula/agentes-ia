from fastapi import APIRouter, Body, Depends, UploadFile, File
from typing import List

from app.api.controllers.RagController import RagController
from app.auth import UsuarioAutenticado, requiere_admin

#: Toda la gestión de la base de conocimiento es de administración. Antes este
#: router estaba abierto: cualquiera que conociera la URL podía subir o borrar
#: documentos de los que luego se fía el agente para responder.
router = APIRouter(
    prefix="/rag",
    tags=["RAG"],
    dependencies=[Depends(requiere_admin)],
)


@router.get("/kb")
async def ver_base_conocimiento():
    """Vista completa: categorías en orden de consulta y documentos de cada una."""
    return RagController.kb_resumen()


@router.put("/kb/orden")
async def cambiar_orden(orden: list[str] = Body(..., embed=True)):
    """Cambia en qué orden se consultan las categorías."""
    return RagController.set_orden(orden)


@router.put("/kb/{perfil}/{nombre_archivo}/activo")
async def cambiar_activo(perfil: str, nombre_archivo: str, activo: bool = Body(..., embed=True)):
    """Retira un documento de las consultas, o vuelve a ponerlo en juego."""
    return RagController.set_activo(perfil, nombre_archivo, activo)


@router.post("/upload/{perfil}")
async def subir_documentos(
    perfil: str,
    files: List[UploadFile] = File(...),
    usuario: UsuarioAutenticado = Depends(requiere_admin),
):
    return await RagController.upload_documents(
        perfil, files, usuario=usuario.email or usuario.nombre
    )


@router.get("/documents/{perfil}")
async def listar_documentos(perfil: str):
    return await RagController.list_documents(perfil)


@router.delete("/documents/{perfil}/{nombre_archivo}")
async def borrar_documento(perfil: str, nombre_archivo: str):
    return await RagController.delete_document(perfil, nombre_archivo)
