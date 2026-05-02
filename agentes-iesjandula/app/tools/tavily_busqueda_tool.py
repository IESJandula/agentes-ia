import os
from dotenv import load_dotenv
from langchain_tavily import TavilySearch

load_dotenv()

api_key = os.getenv("TAVILY_API_KEY")

if api_key is None:
    print("⚠️ No se encontró TAVILY_API_KEY en el archivo .env")
else:
    os.environ["TAVILY_API_KEY"] = api_key

from langchain_core.tools import tool

# Herramienta base de Tavily (privada, se usará dentro de los wrappers)
_tavily_centro = TavilySearch(
    max_results=5,
    tavily_api_key=api_key,
    include_domains=[
        "blogsaverroes.juntadeandalucia.es",  # Blog principal del centro (noticias, eventos)
        "fp.iesjandula.es",                    # Web de FP (ciclos formativos, asignaturas)
        "iesjandula.es",                       # Web institucional
        "www.iesjandula.es"                    # Variante con www
    ],
    name="busqueda_web_ies_jandula_raw",
)

_tavily_general = TavilySearch(
    max_results=3,
    tavily_api_key=api_key,
    name="busqueda_web_general_raw",
)

@tool
def busqueda_web_ies_jandula(search: str) -> str:
    """Busca información en la web oficial del IES Jándula (blog Averroes).
    USA ESTA HERRAMIENTA para: noticias del centro, eventos, actividades extraescolares,
    horarios generales, matrículas, secretaría, plazos, FP, ciclos formativos,
    calendario escolar, y cualquier información pública del IES Jándula.
    NO necesitas añadir 'site:' a la consulta, el filtro de dominio se aplica automáticamente.
    Añade el año '2025' o '2026' a tu búsqueda para obtener resultados actualizados."""
    print(f"\n🌐 [TOOL: busqueda_web_ies_jandula] Query: {search}")
    resultado = _tavily_centro.invoke(search)
    print(f"   [DEBUG] Resultados obtenidos (Tavily Centro): {str(resultado)[:200]}...")
    return str(resultado)

@tool
def busqueda_web_general(search: str) -> str:
    """Busca información GENERAL en internet.
    USA ESTA HERRAMIENTA SOLO cuando la consulta NO sea sobre el IES Jándula directamente,
    por ejemplo: normativa educativa de la Junta de Andalucía, legislación estatal (LOMLOE),
    fechas de oposiciones, información de Séneca/iPasen, o temas educativos generales.
    Para información específica del IES Jándula, usa 'busqueda_web_ies_jandula' en su lugar."""
    print(f"\n🌍 [TOOL: busqueda_web_general] Query: {search}")
    resultado = _tavily_general.invoke(search)
    print(f"   [DEBUG] Resultados obtenidos (Tavily General): {str(resultado)[:200]}...")
    return str(resultado)

# Exportamos las funciones decoradas
tool_busqueda_web_centro = busqueda_web_ies_jandula
tool_busqueda_general = busqueda_web_general