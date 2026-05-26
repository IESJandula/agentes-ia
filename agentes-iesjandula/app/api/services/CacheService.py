"""
CacheService.py — Caché TTL en memoria para respuestas frecuentes.
Evita llamadas repetidas a Gemini para preguntas idénticas o muy similares.
"""
import hashlib
from datetime import datetime, timedelta


class CacheService:
    def __init__(self, ttl_minutos: int = 30, max_entradas: int = 200):
        self._cache: dict = {}
        self._ttl = timedelta(minutes=ttl_minutos)
        self._max = max_entradas

    def _clave(self, pregunta: str, perfil: str) -> str:
        texto = f"{perfil}:{pregunta.lower().strip()}"
        return hashlib.md5(texto.encode()).hexdigest()

    def get(self, pregunta: str, perfil: str) -> dict | None:
        key = self._clave(pregunta, perfil)
        if key in self._cache:
            entry = self._cache[key]
            if datetime.now() - entry["timestamp"] < self._ttl:
                print(f"✅ [CACHE] Hit: '{pregunta[:60]}'")
                return entry["datos"]
            del self._cache[key]
        return None

    def set(self, pregunta: str, perfil: str, datos: dict) -> None:
        # Evitar desbordamiento: eliminar la entrada más antigua si se supera el límite
        if len(self._cache) >= self._max:
            oldest = min(self._cache, key=lambda k: self._cache[k]["timestamp"])
            del self._cache[oldest]

        key = self._clave(pregunta, perfil)
        self._cache[key] = {"datos": datos, "timestamp": datetime.now()}
        print(f"💾 [CACHE] Guardado: '{pregunta[:60]}'")

    def invalidar_todo(self) -> None:
        self._cache.clear()
        print("🗑️ [CACHE] Caché vaciado.")

    def stats(self) -> dict:
        ahora = datetime.now()
        activas = sum(
            1 for e in self._cache.values()
            if ahora - e["timestamp"] < self._ttl
        )
        return {"entradas_totales": len(self._cache), "entradas_activas": activas}


cache_service = CacheService(ttl_minutos=30)
