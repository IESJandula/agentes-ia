from langchain_core.tools import tool
from data import vector_store

@tool
def guia_profesorado(search: str) -> str:
    """Consulta la guía oficial del profesorado del IES Jándula 2025/26.

    Args:
        search (str): La consulta de búsqueda.

    Returns: 
        str: La información relevante encontrada en la guía.
    """
    print("Buscando en la guia de profesorado:",search)
    docs = vector_store.similarity_search(search, k=10)
    return " ".join(("\n\n".join([doc.page_content for doc in docs])).split())