from langchain_core.tools import tool
from data.data import profesores_col


@tool
def guia_profesorado(search: str) -> str:
    """Consulta la guía oficial del profesorado del IES Jándula 2025/26.

    USA ESTA HERRAMIENTA SOLO para preguntas sobre:
    - Guardias, sustituciones y partes de ausencia docente
    - Nombres de profesores, tutores y cargos directivos
    - Protocolo de actuación ante incidencias con alumnado
    - Normativa interna: NOF, PEC, PGA, ROF
    - CCP, departamentos didácticos y reuniones de coordinación
    - Evaluaciones: criterios, actas y procedimientos de calificación
    - Protocolo de atención a la diversidad (PT, AL, NEAE)
    - Plan de convivencia visto desde el rol docente
    - Horario del profesorado, guardias de recreo y puertas

    NO USAR para: información general del centro, noticias,
    eventos públicos, actividades extraescolares ni dudas del alumnado.

    Args:
        search (str): La consulta de búsqueda o palabras clave.

    Returns:
        str: Información relevante de la guía del profesorado.
    """
    print(f"📋 Buscando en guía de profesorado: {search}")

    count = profesores_col.count()
    print(f"DEBUG: La colección tiene {count} fragmentos.")

    resultados = profesores_col.query(
        query_texts=[search],
        n_results=8,
        include=["documents", "metadatas", "distances"]
    )

    docs = resultados["documents"][0]

    if not docs:
        return "No se encontró información en la guía del profesorado para esa consulta."

    contexto = ""
    for i, texto in enumerate(docs):
        contexto += f"\n--- Fragmento {i+1} ---\n{texto}\n"

    return contexto