from langchain_core.tools import tool
from data.data import alumnos_col

@tool
def guia_alumnado(search: str) -> str:
    """Consulta los documentos de ayuda o datos de interés
     para los alumnos del IES Jándula 2025/26.

    Args:
        search (str): La consulta de búsqueda.

    Returns: 
        str: La información relevante encontrada en la guía.
    """
    print("Buscando en la guia de profesorado:",search)
    docs = alumnos_col.similarity_search(search, k=10)
    return " ".join(("\n\n".join([doc.page_content for doc in docs])).split())