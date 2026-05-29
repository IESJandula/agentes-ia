"""
legislacion_tool.py — IES Jándula
Búsqueda especializada en fuentes legislativas oficiales españolas:
BOE, BOJA, portal de Educación de la Junta de Andalucía y TodoFP.
"""
import os
from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()

_api_key = os.getenv("TAVILY_API_KEY")
_client = None

if _api_key:
    from tavily import TavilyClient
    _client = TavilyClient(api_key=_api_key)
else:
    print("⚠️ TAVILY_API_KEY no configurada — busqueda_legislacion_educativa desactivada.")

# Dominios de fuentes legislativas y educativas oficiales
_DOMINIOS_LEGISLACION = [
    "boe.es",
    "boja.juntadeandalucia.es",
    "juntadeandalucia.es",
    "educacion.juntadeandalucia.es",
    "todofp.es",
    "sede.educacion.gob.es",
    "mecd.gob.es",
]


@tool
def busqueda_legislacion_educativa(query: str) -> str:
    """Busca legislación y normativa educativa en fuentes oficiales españolas.

    USA ESTA HERRAMIENTA para:
    - Leyes educativas: LOMLOE, LOE, LOGSE, Estatuto Docente
    - Decretos y órdenes de la Junta de Andalucía sobre educación
    - Instrucciones de inicio de curso (Junta de Andalucía)
    - Normativa sobre evaluación, titulación y acceso a ciclos formativos
    - Derechos y deberes del profesorado y alumnado (marco legal)
    - Convocatorias de oposiciones y concursos docentes (BOE/BOJA)
    - Legislación sobre FP: Ley Orgánica 3/2022, catálogos de ciclos
    - Normativa sobre NEAE, inclusión, convivencia escolar

    Fuentes consultadas: BOE, BOJA, Educación Junta de Andalucía, TodoFP.

    Args:
        query (str): Consulta legislativa. Incluye el nombre exacto de la ley, decreto
                     u orden si lo conoces (ej: "LOMLOE artículo 28 evaluación ESO").

    Returns:
        str: Fragmentos legislativos relevantes con su fuente oficial.
    """
    if not _client:
        return "Error: TAVILY_API_KEY no configurada."

    print(f"\n⚖️  [TOOL: busqueda_legislacion_educativa] Query: {query}")

    try:
        # 1. Búsqueda en dominios legislativos oficiales
        print("   🔍 Buscando en fuentes legislativas oficiales...")
        response = _client.search(
            query=query + " educación España",
            search_depth="advanced",
            max_results=8,
            include_domains=_DOMINIOS_LEGISLACION,
        )

        # Si hay pocos resultados, ampliar con búsqueda general legislativa
        if not response.get("results") or len(response["results"]) < 2:
            print("   ⚠️ Pocos resultados en dominios oficiales. Ampliando búsqueda...")
            response = _client.search(
                query=query + " normativa educativa España 2025",
                search_depth="advanced",
                max_results=8,
            )

        resultados = response.get("results", [])
        if not resultados:
            return "No se encontró legislación relevante para esta consulta."

        contexto = []
        for res in resultados:
            contexto.append(
                f"FUENTE: {res['url']}\n"
                f"TÍTULO: {res['title']}\n"
                f"CONTENIDO: {res['content']}\n"
            )

        print(f"   ✅ [LEGISLACIÓN] {len(contexto)} fuentes encontradas.")
        return "\n---\n".join(contexto)

    except Exception as e:
        print(f"   ❌ [LEGISLACIÓN] Error: {e}")
        return f"Error al buscar legislación: {e}"
