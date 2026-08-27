"""
KbService.py — Gobierno de la base de conocimiento.

Responde a dos preguntas que antes no tenían dueño:

  1. ¿QUÉ hay indexado y en qué categoría? ChromaDB lo sabe, pero no guarda
     quién subió cada documento ni cuándo, y esas dos columnas son lo primero
     que se pregunta cuando alguien ve un PDF raro en la base.

  2. ¿EN QUÉ ORDEN se consulta? La prioridad es POR CATEGORÍA, no por documento:
     primero la documentación del centro, luego la legislación oficial y, solo
     si hace falta, el conocimiento aprendido de la web. Dentro de una categoría
     manda la relevancia semántica, que para eso está.

El orden y los documentos retirados viven en ``data/kb_config.json`` (mismo
patrón que ``usage_stats.json``): es estado de ejecución, no código, y tiene que
poder cambiarse desde el panel sin un redeploy.

La lista de documentos NO se guarda aquí: la fuente de verdad de qué está
indexado es ChromaDB. Este registro solo añade los metadatos que Chroma no tiene
y recuerda qué se ha retirado.
"""
import json
import os
import threading
from datetime import datetime

from data.data import contar_fragmentos_por_documento

CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "kb_config.json"
)

#: Categoría → (etiqueta para el panel, descripción de para qué sirve).
#: Las claves son los mismos perfiles que ya entiende `_PERFIL_A_COLECCION`.
CATEGORIAS: dict[str, tuple[str, str]] = {
    "centro": (
        "Información del centro",
        "Oferta educativa, ciclos, servicios, trámites de secretaría.",
    ),
    "profesores": (
        "Guía del profesorado",
        "Normativa interna, guardias, evaluación, cargos y protocolos.",
    ),
    "alumnos": (
        "Guía del alumnado",
        "Convivencia, horarios, actividades, becas y trámites del alumnado.",
    ),
    "legislacion": (
        "Legislación oficial",
        "LOMLOE, decretos, currículos y órdenes de BOE/BOJA.",
    ),
    "conocimiento": (
        "Conocimiento web aprendido",
        "Fragmentos que el agente ha indexado solo, a partir de búsquedas web.",
    ),
}

#: Orden por defecto: lo curado antes que lo oficial, y lo oficial antes que lo
#: que el agente ha aprendido por su cuenta de internet, que es lo más ruidoso.
ORDEN_POR_DEFECTO = ["centro", "profesores", "alumnos", "legislacion", "conocimiento"]

_lock = threading.Lock()


def _cargar() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                cfg.setdefault("orden", list(ORDEN_POR_DEFECTO))
                cfg.setdefault("documentos", {})
                return cfg
        except Exception as e:
            print(f"⚠️ [KB] kb_config.json ilegible ({e}). Se usa la configuración por defecto.")
    return {"orden": list(ORDEN_POR_DEFECTO), "documentos": {}}


def _guardar(cfg: dict) -> None:
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_PATH)  # atómico: nunca deja el config a medias


def _clave(categoria: str, archivo: str) -> str:
    return f"{categoria}/{archivo}"


class KbService:
    def __init__(self):
        self._cfg = _cargar()

    # -- Orden de consulta ---------------------------------------------------

    def orden(self) -> list[str]:
        """Categorías en el orden en que deben consultarse.

        Se sanea en cada lectura: si alguien edita el JSON a mano y se deja una
        categoría fuera, se añade al final en vez de desaparecer de la búsqueda.
        """
        guardado = [c for c in self._cfg.get("orden", []) if c in CATEGORIAS]
        faltantes = [c for c in ORDEN_POR_DEFECTO if c not in guardado]
        return guardado + faltantes

    def set_orden(self, nuevo: list[str]) -> list[str]:
        desconocidas = [c for c in nuevo if c not in CATEGORIAS]
        if desconocidas:
            raise ValueError(f"Categorías desconocidas: {', '.join(desconocidas)}")
        if len(set(nuevo)) != len(nuevo):
            raise ValueError("Hay categorías repetidas en el orden.")
        with _lock:
            self._cfg["orden"] = list(nuevo)
            _guardar(self._cfg)
        return self.orden()

    # -- Estado de cada documento -------------------------------------------

    def esta_activo(self, categoria: str, archivo: str) -> bool:
        """Un documento se considera activo mientras no se retire explícitamente."""
        meta = self._cfg["documentos"].get(_clave(categoria, archivo))
        return True if meta is None else bool(meta.get("activo", True))

    def inactivos(self, categoria: str) -> set[str]:
        """Archivos retirados de una categoría. Lo consultan las tools en caliente."""
        prefijo = f"{categoria}/"
        return {
            k[len(prefijo):]
            for k, v in self._cfg["documentos"].items()
            if k.startswith(prefijo) and not v.get("activo", True)
        }

    def set_activo(self, categoria: str, archivo: str, activo: bool) -> dict:
        with _lock:
            meta = self._cfg["documentos"].setdefault(_clave(categoria, archivo), {})
            meta["activo"] = bool(activo)
            _guardar(self._cfg)
        return {"categoria": categoria, "archivo": archivo, "activo": bool(activo)}

    def registrar_subida(self, categoria: str, archivo: str, usuario: str | None) -> None:
        """Anota autoría y fecha. Chroma no las guarda y en una base compartida
        por medio claustro son justo las dos columnas que hacen falta."""
        with _lock:
            self._cfg["documentos"][_clave(categoria, archivo)] = {
                "activo": True,
                "subido_por": usuario or "desconocido",
                "subido_en": datetime.now().isoformat(timespec="seconds"),
            }
            _guardar(self._cfg)

    def olvidar(self, categoria: str, archivo: str) -> None:
        """Limpia el registro de un documento ya borrado de ChromaDB."""
        with _lock:
            if self._cfg["documentos"].pop(_clave(categoria, archivo), None) is not None:
                _guardar(self._cfg)

    # -- Vista completa para el panel ---------------------------------------

    def resumen(self) -> dict:
        """Toda la base de conocimiento, categoría a categoría y en orden."""
        categorias = []
        for posicion, cat in enumerate(self.orden(), start=1):
            etiqueta, descripcion = CATEGORIAS[cat]
            try:
                conteo = contar_fragmentos_por_documento(cat)
            except Exception as e:
                print(f"⚠️ [KB] No se pudo leer la categoría '{cat}': {e}")
                conteo = {}

            documentos = []
            for archivo in sorted(conteo):
                meta = self._cfg["documentos"].get(_clave(cat, archivo), {})
                documentos.append({
                    "archivo": archivo,
                    "fragmentos": conteo[archivo],
                    "activo": bool(meta.get("activo", True)),
                    "subido_por": meta.get("subido_por"),
                    "subido_en": meta.get("subido_en"),
                })

            categorias.append({
                "categoria": cat,
                "etiqueta": etiqueta,
                "descripcion": descripcion,
                "posicion": posicion,
                "documentos": documentos,
                "total_documentos": len(documentos),
                "total_fragmentos": sum(conteo.values()),
                "activos": sum(1 for d in documentos if d["activo"]),
            })

        return {
            "orden": self.orden(),
            "categorias": categorias,
            "total_documentos": sum(c["total_documentos"] for c in categorias),
            "total_fragmentos": sum(c["total_fragmentos"] for c in categorias),
        }


# Instancia singleton
kb_service = KbService()
