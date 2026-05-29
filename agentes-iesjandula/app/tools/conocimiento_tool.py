"""
conocimiento_tool.py — IES Jándula
Consulta la base de conocimiento que el agente va construyendo automáticamente
a partir de búsquedas web previas. Actúa como caché semántico persistente.
"""
from langchain_core.tools import tool
from data.data import obtener_coleccion, query_coleccion


@tool
def consultar_conocimiento_aprendido(search: str) -> str:
    """Consulta la base de conocimiento construida automáticamente de búsquedas previas.

    Contiene legislación educativa, normativas, respuestas de BOE/BOJA y otros
    documentos descubiertos en consultas anteriores de profesores.

    USA ESTA HERRAMIENTA PRIMERO antes de buscar en internet:
    - Es más rápida (no consume API de búsqueda)
    - Contiene exactamente lo que se ha consultado antes en este centro
    - Si devuelve resultados relevantes, no es necesario buscar en la web

    Args:
        search (str): Término o pregunta a buscar en el conocimiento acumulado.

    Returns:
        str: Fragmentos relevantes del conocimiento aprendido, o indicación de que
             no hay información disponible.
    """
    print(f"\n🧠 [TOOL: consultar_conocimiento_aprendido] Query: {search}")

    try:
        col = obtener_coleccion("conocimiento")
        if col.count() == 0:
            return "La base de conocimiento aprendido aún está vacía. Usa las herramientas de búsqueda web."

        resultados = query_coleccion(
            col,
            query=search,
            n_results=6,
            include=["documents", "metadatas", "distances"],
        )

        docs       = resultados["documents"][0] if resultados.get("documents") else []
        metadatas  = resultados["metadatas"][0]  if resultados.get("metadatas") else []
        distancias = resultados["distances"][0]  if resultados.get("distances") else []

        if not docs:
            return "No se encontró información relevante en el conocimiento aprendido."

        # Filtrar por relevancia
        THRESHOLD = 1.1
        pares = [
            (d, m, dist)
            for d, m, dist in zip(docs, metadatas, distancias)
            if dist <= THRESHOLD
        ]

        if not pares:
            return "No se encontró información suficientemente relevante. Prueba con las herramientas de búsqueda web."

        contexto = f"Información del conocimiento aprendido ({len(pares)} fragmentos):\n"
        for i, (texto, meta, dist) in enumerate(pares):
            titulo  = meta.get("titulo", "Sin título")[:100]
            url     = meta.get("source_url", "")
            fecha   = meta.get("fecha_indexado", "")
            relevancia = max(0.0, 1.0 - dist)
            contexto += (
                f"\n--- Fragmento {i+1} "
                f"[Fuente: {url}] "
                f"(Título: {titulo}) "
                f"(Relevancia: {relevancia:.2f}) ---\n{texto}\n"
            )

        print(f"   ✅ [CONOCIMIENTO] {len(pares)} fragmentos relevantes encontrados.")
        return contexto

    except Exception as e:
        print(f"   ❌ [CONOCIMIENTO] Error: {e}")
        return f"Error consultando conocimiento aprendido: {e}"
