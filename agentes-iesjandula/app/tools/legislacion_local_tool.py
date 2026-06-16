"""
legislacion_local_tool.py — IES Jándula
Consulta la colección LIMPIA de legislación (los 90 PDFs oficiales del seed:
LOMLOE, decretos, currículos, órdenes BOJA/BOE, etc.).

A diferencia de 'consultar_conocimiento_aprendido' (que lee 'conocimiento_web',
el caché auto-aprendido de búsquedas web y por tanto más ruidoso), esta tool
consulta SOLO la legislación oficial indexada, sin contaminación.
"""
from langchain_core.tools import tool
from data.data import obtener_coleccion, query_coleccion


@tool
def consultar_legislacion(search: str) -> str:
    """Consulta la base LOCAL de legislación educativa oficial del IES Jándula.

    Contiene los documentos oficiales indexados: LOE/LOMLOE, LO 3/2022 de FP,
    reales decretos, currículos de ESO/Bachillerato/FP, órdenes de la Junta de
    Andalucía (BOJA), permisos docentes, normativa de evaluación, etc.

    USA ESTA HERRAMIENTA ANTES de buscar en internet para cualquier pregunta
    sobre leyes, decretos, órdenes, currículos, evaluación o normativa educativa.
    Es la fuente más fiable y específica de Andalucía.

    Args:
        search (str): Término o pregunta a buscar en la legislación indexada.

    Returns:
        str: Fragmentos relevantes de la legislación oficial, o indicación de que
             no hay información suficientemente relevante.
    """
    print(f"\n⚖️  [TOOL: consultar_legislacion] Query: {search}")

    try:
        col = obtener_coleccion("legislacion")
        if col.count() == 0:
            return ("La base de legislación local aún no está indexada. "
                    "Usa 'busqueda_legislacion_educativa' para buscar en BOE/BOJA.")

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
            return "No se encontró legislación relevante. Prueba con 'busqueda_legislacion_educativa'."

        THRESHOLD = 1.1
        pares = [
            (d, m, dist)
            for d, m, dist in zip(docs, metadatas, distancias)
            if dist <= THRESHOLD
        ]

        if not pares:
            return ("No se encontró legislación suficientemente relevante en la base local. "
                    "Prueba con 'busqueda_legislacion_educativa' (BOE/BOJA).")

        contexto = f"Legislación oficial indexada ({len(pares)} fragmentos):\n"
        for i, (texto, meta, dist) in enumerate(pares):
            fuente     = meta.get("source", meta.get("titulo", "documento"))
            nombre     = fuente.split("/")[-1] if fuente else "documento"
            relevancia = max(0.0, 1.0 - dist)
            contexto += (
                f"\n--- Fragmento {i+1} "
                f"[Fuente: {nombre}] "
                f"(Relevancia: {relevancia:.2f}) ---\n{texto}\n"
            )

        print(f"   ✅ [LEGISLACION] {len(pares)} fragmentos relevantes encontrados.")
        return contexto

    except Exception as e:
        print(f"   ❌ [LEGISLACION] Error: {e}")
        return f"Error consultando legislación local: {e}"
