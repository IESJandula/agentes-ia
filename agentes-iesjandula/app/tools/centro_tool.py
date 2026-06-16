"""
centro_tool.py — IES Jándula
Consulta la base de documentos INSTITUCIONALES CURADOS del centro
(colección 'centro_info'): oferta educativa, ciclos formativos, servicios,
horarios generales, trámites de secretaría, etc.

Es la fuente preferente para preguntas públicas sobre el IES Jándula, por
delante de las búsquedas web (que pueden devolver blogs o info desactualizada).
"""
from langchain_core.tools import tool
from data.data import obtener_coleccion, query_coleccion


@tool
def consultar_info_centro(search: str) -> str:
    """Consulta la información oficial y curada del IES Jándula.

    Contiene los documentos institucionales del centro: oferta educativa y
    ciclos formativos (FP Básica, Grado Medio, Grado Superior), servicios
    (comedor, transporte, biblioteca), horarios generales, trámites de
    secretaría, matrícula y admisión.

    USA ESTA HERRAMIENTA PRIMERO para cualquier pregunta pública sobre el
    centro (qué ciclos hay, oferta educativa, servicios, trámites). Es más
    fiable y específica que buscar en internet.

    Args:
        search (str): Término o pregunta sobre el centro.

    Returns:
        str: Fragmentos relevantes de la documentación del centro, o indicación
             de que no hay información indexada (entonces usa la búsqueda web).
    """
    print(f"\n🏫 [TOOL: consultar_info_centro] Query: {search}")

    try:
        col = obtener_coleccion("centro")
        if col.count() == 0:
            return ("No hay documentación del centro indexada todavía. "
                    "Usa 'busqueda_web_ies_jandula' para buscar en la web oficial.")

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
            return "No se encontró información del centro. Prueba con 'busqueda_web_ies_jandula'."

        THRESHOLD = 1.1
        pares = [
            (d, m, dist)
            for d, m, dist in zip(docs, metadatas, distancias)
            if dist <= THRESHOLD
        ]

        if not pares:
            return ("No se encontró información del centro suficientemente relevante. "
                    "Usa 'busqueda_web_ies_jandula'.")

        contexto = f"Información oficial del IES Jándula ({len(pares)} fragmentos):\n"
        for i, (texto, meta, dist) in enumerate(pares):
            fuente     = meta.get("source", meta.get("titulo", "documento del centro"))
            nombre     = str(fuente).split("/")[-1] if fuente else "documento del centro"
            relevancia = max(0.0, 1.0 - dist)
            contexto += (
                f"\n--- Fragmento {i+1} "
                f"[Fuente: {nombre}] "
                f"(Relevancia: {relevancia:.2f}) ---\n{texto}\n"
            )

        print(f"   ✅ [CENTRO] {len(pares)} fragmentos relevantes encontrados.")
        return contexto

    except Exception as e:
        print(f"   ❌ [CENTRO] Error: {e}")
        return f"Error consultando información del centro: {e}"
