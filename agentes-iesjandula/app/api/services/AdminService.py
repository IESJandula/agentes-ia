"""
AdminService.py — Registro de uso y estadísticas del agente.
Persiste los datos en data/usage_stats.json para sobrevivir reinicios.
"""
import json
import os
from datetime import datetime
from typing import Optional

STATS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "usage_stats.json")
MAX_QUERIES_LOG = 100  # Máximo de consultas guardadas en el log


def _cargar_stats() -> dict:
    if os.path.exists(STATS_PATH):
        try:
            with open(STATS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "total": {"profesores": 0, "alumnos": 0},
        "sin_resultado": {"profesores": 0, "alumnos": 0},
        "queries": [],
    }


def _guardar_stats(stats: dict) -> None:
    os.makedirs(os.path.dirname(STATS_PATH), exist_ok=True)
    with open(STATS_PATH, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


class AdminService:
    def __init__(self):
        self._stats = _cargar_stats()

    def registrar_consulta(
        self,
        pregunta: str,
        perfil: str,
        fuentes: list[str],
        desde_cache: bool = False,
        tiempo_ms: Optional[int] = None,
    ) -> None:
        perfil_key = perfil if perfil in ("profesores", "alumnos") else "alumnos"

        # Incrementar contadores
        self._stats["total"][perfil_key] = self._stats["total"].get(perfil_key, 0) + 1
        sin_resultado = len(fuentes) == 0
        if sin_resultado:
            self._stats["sin_resultado"][perfil_key] = (
                self._stats["sin_resultado"].get(perfil_key, 0) + 1
            )

        # Añadir al log rotativo
        entrada = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "pregunta": pregunta[:200],
            "perfil": perfil_key,
            "fuentes": fuentes,
            "sin_resultado": sin_resultado,
            "desde_cache": desde_cache,
            "tiempo_ms": tiempo_ms,
        }
        self._stats["queries"].insert(0, entrada)
        if len(self._stats["queries"]) > MAX_QUERIES_LOG:
            self._stats["queries"] = self._stats["queries"][:MAX_QUERIES_LOG]

        _guardar_stats(self._stats)

    def get_stats(self) -> dict:
        total_general = sum(self._stats["total"].values())
        sin_resultado_total = sum(self._stats["sin_resultado"].values())
        return {
            "total": self._stats["total"],
            "total_general": total_general,
            "sin_resultado": self._stats["sin_resultado"],
            "sin_resultado_total": sin_resultado_total,
            "tasa_sin_resultado": (
                round(sin_resultado_total / total_general * 100, 1)
                if total_general > 0 else 0
            ),
        }

    def get_queries(self, limite: int = 50, solo_sin_resultado: bool = False) -> list:
        queries = self._stats["queries"]
        if solo_sin_resultado:
            queries = [q for q in queries if q["sin_resultado"]]
        return queries[:limite]


admin_service = AdminService()
