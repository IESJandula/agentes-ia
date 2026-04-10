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

    resultados = profesores_col.query(
        query_texts=[search],
        n_results=8,
        include=["documents", "metadatas", "distances"]
    )

    docs      = resultados["documents"][0]
    distancias = resultados["distances"][0]

    print(f"   [DEBUG] Se encontraron {len(docs)} fragmentos.")
    for i, (d, dist) in enumerate(zip(docs[:3], distancias[:3])):
        print(f"   [DEBUG] Fragmento {i+1} (dist: {dist:.4f}): {d[:100]}...")

    if not docs:
        return "No se encontró información en la guía del profesorado para esa consulta."

    # Filtra resultados con distancia muy alta (semánticamente irrelevantes)
    THRESHOLD = 1.4
    pares = [(d, dist) for d, dist in zip(docs, distancias) if dist <= THRESHOLD]

    if not pares:
        return "No se encontró información suficientemente relevante en la guía del profesorado."

    contexto = ""
    for i, (texto, dist) in enumerate(pares):
        contexto += f"\n--- Fragmento {i+1} (relevancia: {1 - dist:.2f}) ---\n{texto}\n"

    return contexto