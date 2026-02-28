from .guia_profesorado_tool import guia_profesorado
from .guia_alumnado_tool import guia_alumnado
from .tavily_busqueda_tool import tool_busqueda_general
from .respuesta_final_tool import dar_respuesta_final
from .playwright_busqueda_tool import get_playwright_tools

#CAMBIAR EL PARÁMETRO DE PERFIL POR DEFECTO A alumnos cuando todo esté listo
async def obtener_todas_las_tools(perfil: str = "profesores"):
    """
    Filtra las herramientas según el perfil del usuario.
    """
    herramientas = [
        tool_busqueda_general,
        dar_respuesta_final,
        guia_alumnado
    ]
    
    if perfil == "profesores":
        herramientas.append(guia_profesorado)
    
    try:
        herramientas_navegador = await get_playwright_tools()
        herramientas.extend(herramientas_navegador)
    except Exception as e:
        print(f"⚠️ Error cargando Playwright: {e}")
    
    return herramientas