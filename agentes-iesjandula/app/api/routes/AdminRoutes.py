from fastapi import APIRouter
from app.api.controllers.AdminController import AdminController

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/stats")
async def obtener_estadisticas():
    return AdminController.get_stats()


@router.get("/queries")
async def obtener_consultas(limite: int = 50, solo_sin_resultado: bool = False):
    return AdminController.get_queries(limite=limite, solo_sin_resultado=solo_sin_resultado)


@router.delete("/cache")
async def limpiar_cache():
    return AdminController.limpiar_cache()
