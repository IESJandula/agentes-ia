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
    docs = alumnos_col.similarity_search(search, k=8)

    if not docs:
        return "No se encontró información en la guía del alumnado para esa consulta."

    contexto = ""
    for i, doc in enumerate(docs):
        contexto += f"\n--- Fragmento {i+1} ---\n{doc.page_content}\n"

    return contexto