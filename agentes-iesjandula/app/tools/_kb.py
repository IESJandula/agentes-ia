"""
_kb.py — puente entre las tools y el gobierno de la base de conocimiento.

Las tools consultan ChromaDB; el panel decide qué documentos siguen en juego.
Este módulo traduce lo segundo a un filtro que entiende lo primero.

Es privado (guion bajo) a propósito: no es una tool, no se le pasa al LLM.
"""


def filtro_activos(categoria: str) -> dict | None:
    """Filtro ``where`` de ChromaDB que excluye los documentos retirados.

    Devuelve ``None`` cuando no hay ninguno retirado, que es el caso normal:
    así la consulta va sin filtro y no paga nada por una función que casi
    siempre no tiene nada que hacer.

    El import va dentro por el mismo motivo que en ``app/tools/__init__.py``:
    `app.api.services` importa `app.agents`, que importa las tools. A nivel de
    módulo esto cerraría el ciclo según por dónde se entre.
    """
    from app.api.services.KbService import kb_service

    retirados = kb_service.inactivos(categoria)
    if not retirados:
        return None
    return {"source": {"$nin": sorted(retirados)}}
