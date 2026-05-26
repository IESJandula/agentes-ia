from app.api.services.AdminService import admin_service
from app.api.services.CacheService import cache_service


class AdminController:

    @staticmethod
    def get_stats() -> dict:
        stats = admin_service.get_stats()
        cache = cache_service.stats()
        return {**stats, "cache": cache}

    @staticmethod
    def get_queries(limite: int = 50, solo_sin_resultado: bool = False) -> dict:
        queries = admin_service.get_queries(limite=limite, solo_sin_resultado=solo_sin_resultado)
        return {"queries": queries, "total": len(queries)}

    @staticmethod
    def limpiar_cache() -> dict:
        cache_service.invalidar_todo()
        return {"status": "ok", "mensaje": "Caché vaciado correctamente."}
