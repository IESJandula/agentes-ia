from langchain_core.tools import tool
from data.data import obtener_coleccion, query_coleccion

# Umbral de distancia semántica — fragmentos con distancia > THRESHOLD se descartan como ruido.
# En espacio L2/coseno de ChromaDB, 1.2 ≈ relevancia mínima aceptable.
_THRESHOLD = 1.2


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
    print(f"\n📚 [TOOL: guia_alumnado] Query: {search}")

    resultados = query_coleccion(
        obtener_coleccion("alumnos"),
        query=search,
        n_results=8,
        include=["documents", "metadatas", "distances"],
    )

    docs       = resultados["documents"][0] if resultados["documents"] else []
    metadatas  = resultados["metadatas"][0] if resultados.get("metadatas") else [{}] * len(docs)
    distancias = resultados["distances"][0] if resultados["distances"] else []

    print(f"   [DEBUG] {len(docs)} fragmentos encontrados en Alumnado.")
    for i, (d, dist) in enumerate(zip(docs[:3], distancias[:3])):
        snippet = d[:100].replace('\n', ' ')
        print(f"   [DEBUG] Fragmento {i+1} (dist: {dist:.4f}): {snippet}...")

    if not docs:
        return "No se encontró información en la guía del alumnado para esa consulta."

    # Filtrar por umbral de distancia semántica (como hace guia_profesorado)
    pares = [
        (d, m, dist)
        for d, m, dist in zip(docs, metadatas, distancias)
        if dist <= _THRESHOLD
    ]

    if not pares:
        # Si nada supera el umbral, devolver los 3 mejores de todas formas
        print("   ⚠️ Ningún fragmento supera el threshold; usando los 3 más cercanos.")
        pares = list(zip(docs[:3], metadatas[:3], distancias[:3]))

    contexto = "Información recuperada de la Guía del Alumnado:\n"
    for i, (texto, meta, dist) in enumerate(pares):
        fuente = meta.get("source", "Guía del Alumnado") if meta else "Guía del Alumnado"
        relevancia = max(0.0, 1.0 - dist)
        contexto += (
            f"\n--- Fragmento {i+1} [Fuente: {fuente}] "
            f"(Relevancia: {relevancia:.2f}) ---\n{texto}\n"
        )

    return contexto
