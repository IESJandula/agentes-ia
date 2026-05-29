"""
CacheService.py — Caché TTL en memoria para respuestas frecuentes.
Evita llamadas repetidas a Gemini para preguntas idénticas o muy similares.

Mejoras de normalización:
- Elimina acentos/tildes antes de hashear → "quién es" == "quien es"
- Strip de signos de puntuación iniciales/finales → "¿cómo?" == "como"
- Colapsa espacios múltiples → "hola  mundo" == "hola mundo"
- TTL y max_entradas configurables por variable de entorno
"""
import hashlib
import os
import re
import unicodedata
from datetime import datetime, timedelta


def _normalizar(texto: str) -> str:
    """Normaliza una query para maximizar cache hits ante variaciones menores."""
    # Minúsculas
    t = texto.lower().strip()
    # Eliminar acentos/diacríticos (NFD → quitar categoría Mn)
    t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
    # Eliminar signos de puntuación al inicio/final (¿? ¡!)
    t = t.strip('¿?¡!.,;:')
    # Colapsar espacios múltiples
    t = re.sub(r'\s+', ' ', t)
    return t


class CacheService:
    def __init__(self, ttl_minutos: int | None = None, max_entradas: int | None = None):
        self._cache: dict = {}
        _ttl = int(os.getenv("CACHE_TTL_MINUTOS", ttl_minutos or 30))
        _max = int(os.getenv("CACHE_MAX_ENTRADAS", max_entradas or 300))
        self._ttl = timedelta(minutes=_ttl)
        self._max = _max

    def _clave(self, pregunta: str, perfil: str) -> str:
        texto = f"{perfil}:{_normalizar(pregunta)}"
        return hashlib.sha256(texto.encode()).hexdigest()

    def get(self, pregunta: str, perfil: str) -> dict | None:
        key = self._clave(pregunta, perfil)
        if key in self._cache:
            entry = self._cache[key]
            if datetime.now() - entry["timestamp"] < self._ttl:
                print(f"✅ [CACHE] Hit: '{pregunta[:60]}'")
                return entry["datos"]
            # TTL expirado → limpiar
            del self._cache[key]
        return None

    def set(self, pregunta: str, perfil: str, datos: dict) -> None:
        # Evitar desbordamiento: LRU — eliminar la entrada más antigua
        if len(self._cache) >= self._max:
            oldest = min(self._cache, key=lambda k: self._cache[k]["timestamp"])
            del self._cache[oldest]

        key = self._clave(pregunta, perfil)
        self._cache[key] = {"datos": datos, "timestamp": datetime.now()}
        print(f"💾 [CACHE] Guardado: '{pregunta[:60]}'")

    def invalidar_todo(self) -> None:
        self._cache.clear()
        print("🗑️ [CACHE] Caché vaciado.")

    def limpiar_expirados(self) -> int:
        """Elimina entradas con TTL vencido. Devuelve el número de entradas eliminadas."""
        ahora = datetime.now()
        expirados = [k for k, v in self._cache.items() if ahora - v["timestamp"] >= self._ttl]
        for k in expirados:
            del self._cache[k]
        if expirados:
            print(f"🧹 [CACHE] {len(expirados)} entradas expiradas eliminadas.")
        return len(expirados)

    def stats(self) -> dict:
        ahora = datetime.now()
        activas = sum(
            1 for e in self._cache.values()
            if ahora - e["timestamp"] < self._ttl
        )
        return {
            "entradas_totales": len(self._cache),
            "entradas_activas": activas,
            "ttl_minutos": int(self._ttl.total_seconds() / 60),
            "max_entradas": self._max,
        }


cache_service = CacheService()
