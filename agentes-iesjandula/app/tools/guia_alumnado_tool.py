from langchain_core.tools import tool
from data.data import alumnos_col


@tool
def guia_alumnado(search: str) -> str:
    """Consulta la guía de alumnado del IES Jándula 2025/26.

    USA ESTA HERRAMIENTA para preguntas sobre:
    - Normas de convivencia y derechos del alumnado
    - Horarios de clases, recreos y actividades
    - Servicios del centro: biblioteca, comedor, transporte
    - Actividades extraescolares y complementarias
    - Información para familias y tutores legales
    - Becas, matrículas y trámites administrativos del alumnado
    - Uniforme, material escolar, equipamiento necesario

    NO USAR para: normativa interna del profesorado, guardias,
    sustituciones, actas, CCP, PEC, PGA ni documentos docentes.

    Args:
        search (str): La consulta de búsqueda.

    Returns:
        str: Información relevante de la guía del alumnado.
    """
    print(f"📚 Buscando en guía de alumnado: {search}")
    
    resultados = alumnos_col.query(
        query_texts=[search],
        n_results=8,
        include=["documents", "distances"]
    )
    
    docs = resultados["documents"][0] if resultados["documents"] else []
    distancias = resultados["distances"][0] if resultados["distances"] else []

    print(f"   [DEBUG] Se encontraron {len(docs)} fragmentos en Alumnado.")
    for i, (d, dist) in enumerate(zip(docs[:3], distancias[:3])):
         print(f"   [DEBUG] Fragmento {i+1} (dist: {dist:.4f}): {d[:100]}...")

    if not docs:
        return "No se encontró información en la guía del alumnado para esa consulta."

    contexto = ""
    for i, doc_text in enumerate(docs):
        contexto += f"\n--- Fragmento {i+1} ---\n{doc_text}\n"

    return contexto