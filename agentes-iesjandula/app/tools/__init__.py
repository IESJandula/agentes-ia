from .guia_profesorado_tool import guia_profesorado
from .tavily_busqueda_tool import tool_busqueda_general
from .respuesta_final_tool import dar_respuesta_final
from .playwright_busqueda_tool import get_playwright_tools

def obtener_todas_las_tools():
    """
    Une las herramientas manuales con el conjunto de herramientas 
    de navegación de Playwright.
    """
    # 1. Herramientas manuales (@tool)
    herramientas = [
        guia_profesorado,
        tool_busqueda_general,
        dar_respuesta_final
    ]
    
    try:
        herramientas_navegador = get_playwright_tools()
        herramientas.extend(herramientas_navegador)
    except Exception as e:
        print(f"⚠️ No se pudieron cargar las tools de Playwright: {e}")
    
    return herramientas