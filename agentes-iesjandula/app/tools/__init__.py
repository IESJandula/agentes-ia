from .guia_profesorado_tool import guia_profesorado
from .guia_alumnado_tool import guia_alumnado
from .tavily_busqueda_tool import tool_busqueda_web_centro, tool_busqueda_general
from .playwright_busqueda_tool import extraer_contenido_web
from .legislacion_tool import busqueda_legislacion_educativa
from .conocimiento_tool import consultar_conocimiento_aprendido


async def obtener_tools_publicas() -> list:
    """
    Tools para consultas públicas: web del centro + búsqueda general.
    Disponibles para TODOS los perfiles.
    """
    return [
        consultar_conocimiento_aprendido,   # caché semántico (primero — más rápido)
        guia_alumnado,
        tool_busqueda_web_centro,
        tool_busqueda_general,
        extraer_contenido_web,
    ]


async def obtener_tools_profesorado() -> list:
    """
    Tools para profesores: guía interna, guía alumnado, búsqueda web y legislación.
    """
    return [
        consultar_conocimiento_aprendido,   # caché semántico (primero — más rápido)
        guia_profesorado,
        guia_alumnado,
        tool_busqueda_web_centro,
        tool_busqueda_general,
        extraer_contenido_web,
    ]


async def obtener_tools_legislacion() -> list:
    """
    Tools especializadas para consultas legislativas y normativas.
    Incluye búsqueda en BOE/BOJA y el conocimiento aprendido.
    """
    return [
        consultar_conocimiento_aprendido,   # primero: caché local instantánea
        busqueda_legislacion_educativa,      # BOE, BOJA, Junta de Andalucía
        tool_busqueda_general,               # fallback internet abierto
        guia_profesorado,                    # por si hay normativa interna relacionada
        extraer_contenido_web,               # para leer el texto completo de una ley
    ]


async def obtener_todas_las_tools(perfil: str = "alumnos") -> list:
    """Compatibilidad con código existente."""
    if perfil == "profesores":
        return await obtener_tools_profesorado()
    return await obtener_tools_publicas()
