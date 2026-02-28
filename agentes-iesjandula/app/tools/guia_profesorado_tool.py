from langchain_core.tools import tool
from data.data import profesores_col

@tool
def guia_profesorado(search: str) -> str:
    """Consulta la guía oficial del profesorado del IES Jándula 2025/26.
    Úsala para buscar nombres de profesores, cargos directivos, protocolos de actuación
    y normativas internas del centro.

    Args:
        search (str): La consulta de búsqueda o palabras clave.
    """
    print(f"🔍 Buscando en la guía: {search}")

    print(f"DEBUG: Buscando '{search}' en la colección...")
    
    # Ver cuántos documentos hay en total en la DB
    count = profesores_col._collection.count()
    print(f"DEBUG: La base de datos tiene {count} fragmentos en total.")

    docs = profesores_col.similarity_search(search, k=5)
    print(f"DEBUG: Se han recuperado {len(docs)} fragmentos.")
    
    if len(docs) > 0:
        print(f"DEBUG: Primer fragmento recuperado: {docs[0].page_content[:100]}...")
    
    # 1. Realizamos la búsqueda con k=8 (10 a veces es demasiado contexto y marea al modelo)
    # 2. Nos aseguramos de que los fragmentos mantengan su estructura
    docs = profesores_col.similarity_search(search, k=8)
    
    if not docs:
        return "No se ha encontrado información relevante en la guía del profesorado."

    # 3. Limpieza: Unimos los contenidos con separadores claros para que el LLM distinga los trozos
    contexto = ""
    for i, doc in enumerate(docs):
        contexto += f"\n--- Fragmento {i+1} ---\n{doc.page_content}\n"
    
    return contexto