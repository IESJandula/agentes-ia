from .guia_profesorado_tool import guia_profesorado
from .guia_alumnado_tool import guia_alumnado
from .tavily_busqueda_tool import tool_busqueda_web_centro, tool_busqueda_general
from .playwright_busqueda_tool import extraer_contenido_web


async def obtener_tools_publicas() -> list:
    """
    Tools para consultas públicas: web del centro + búsqueda general.
    Disponibles para TODOS los perfiles.
    """
    herramientas = [
        guia_alumnado,
        tool_busqueda_web_centro,   # búsqueda en la web del IES Jándula
        tool_busqueda_general,       # búsqueda general en internet
        extraer_contenido_web        # nuevo: permite leer webs completas
    ]
    return herramientas


async def obtener_tools_profesorado() -> list:
    """
    Tools para profesores: guía interna, guía alumnado (también accesible) y búsqueda.
    """
    herramientas = [
        guia_profesorado,
        guia_alumnado,
        tool_busqueda_web_centro,   # búsqueda en la web del IES Jándula
        tool_busqueda_general,       # búsqueda general en internet
        extraer_contenido_web        # nuevo: permite leer webs completas
    ]
    return herramientas


async def obtener_todas_las_tools(perfil: str = "alumnos") -> list:
    """
    Devuelve el conjunto completo de tools según el perfil.
    Mantiene compatibilidad con el grafo anterior si aún lo usas.

    Perfiles:
    - "alumnos"    → solo tools públicas
    - "profesores" → tools públicas + guía del profesorado
    """
    tools_publicas = await obtener_tools_publicas()

    if perfil == "profesores":
        tools_prof = await obtener_tools_profesorado()
        return tools_publicas + tools_prof

    return tools_publicas