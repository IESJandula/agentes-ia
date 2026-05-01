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
    print(f"\n📋 [TOOL: guia_profesorado] Query: {search}")

    resultados = profesores_col.query(
        query_texts=[search],
        n_results=8,
        include=["documents", "metadatas", "distances"]
    )

    docs       = resultados["documents"][0]
    metadatas  = resultados["metadatas"][0]
    distancias = resultados["distances"][0]

    print(f"   [DEBUG] Se encontraron {len(docs)} fragmentos.")
    for i, (d, dist) in enumerate(zip(docs[:5], distancias[:5])):
        print(f"   [DEBUG] Fragmento {i+1} (dist: {dist:.4f}): {d[:100].replace('\n', ' ')}...")

    if not docs:
        return "No se encontró información en la guía del profesorado para esa consulta."

    # Filtra resultados con distancia muy alta (semánticamente irrelevantes)
    # En ChromaDB con L2/Cosine, distancias > 1.2 suelen ser ruido
    THRESHOLD = 1.2
    pares = []
    for d, m, dist in zip(docs, metadatas, distancias):
        if dist <= THRESHOLD:
            pares.append((d, m, dist))

    if not pares:
        return "No se encontró información suficientemente relevante en la guía del profesorado."

    contexto = "Información recuperada de la Guía del Profesorado:\n"
    for i, (texto, meta, dist) in enumerate(pares):
        fuente = meta.get("source", "Guía desconocida")
        contexto += f"\n--- Fragmento {i+1} [Fuente: {fuente}] (Relevancia: {max(0, 1 - dist):.2f}) ---\n{texto}\n"

    return contexto