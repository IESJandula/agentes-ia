import asyncio
from app.api.services.AdminService import admin_service
from app.api.services.CacheService import cache_service


class AdminController:

    @staticmethod
    def get_stats() -> dict:
        stats = admin_service.get_stats()
        cache = cache_service.stats()
        seed = admin_service.get_seed_status()
        return {**stats, "cache": cache, "seed": seed}

    @staticmethod
    def get_queries(limite: int = 50, solo_sin_resultado: bool = False) -> dict:
        queries = admin_service.get_queries(limite=limite, solo_sin_resultado=solo_sin_resultado)
        return {"queries": queries, "total": len(queries)}

    @staticmethod
    def limpiar_cache() -> dict:
        cache_service.invalidar_todo()
        return {"status": "ok", "mensaje": "Caché vaciado correctamente."}

    @staticmethod
    def get_seed_status() -> dict:
        return admin_service.get_seed_status()

    @staticmethod
    async def run_seed() -> dict:
        """Lanza el seed de legislación en background desde dentro del proceso de la app."""
        from data.data import seed_legislacion_folder
        asyncio.create_task(asyncio.to_thread(seed_legislacion_folder))
        return {"status": "started", "mensaje": "Seed de legislación iniciado en segundo plano."}
