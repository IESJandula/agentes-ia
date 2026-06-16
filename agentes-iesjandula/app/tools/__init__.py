from .guia_profesorado_tool import guia_profesorado
from .guia_alumnado_tool import guia_alumnado
from .tavily_busqueda_tool import tool_busqueda_web_centro, tool_busqueda_general
from .playwright_busqueda_tool import extraer_contenido_web
from .legislacion_tool import busqueda_legislacion_educativa
from .legislacion_local_tool import consultar_legislacion
from .centro_tool import consultar_info_centro
from .conocimiento_tool import consultar_conocimiento_aprendido


async def obtener_tools_publicas() -> list:
    """
    Tools para consultas públicas: web del centro + búsqueda general.
    Disponibles para TODOS los perfiles.
    """
    return [
        consultar_info_centro,              # 1) docs oficiales curados del centro
        guia_alumnado,
        consultar_conocimiento_aprendido,   #    caché auto-aprendido (web previa)
        tool_busqueda_web_centro,           # 2) web del centro (último recurso)
        tool_busqueda_general,
        extraer_contenido_web,
    ]


async def obtener_tools_profesorado() -> list:
    """
    Tools para profesores: guía interna, guía alumnado, búsqueda web y legislación.
    """
    return [
        guia_profesorado,                   # 1) documentos internos del centro
        consultar_info_centro,              #    info oficial del centro (oferta, servicios)
        guia_alumnado,
        consultar_legislacion,              # 2) legislación oficial indexada (limpia)
        consultar_conocimiento_aprendido,   #    caché auto-aprendido (web previa)
        tool_busqueda_web_centro,           # 3) web (último recurso)
        tool_busqueda_general,
        extraer_contenido_web,
    ]


async def obtener_tools_legislacion() -> list:
    """
    Tools especializadas para consultas legislativas y normativas.
    Incluye búsqueda en BOE/BOJA y el conocimiento aprendido.
    """
    return [
        guia_profesorado,                    # 1) normativa interna del centro (si aplica)
        consultar_legislacion,               # 2) legislación oficial indexada (LIMPIA) — PRIMERO
        consultar_conocimiento_aprendido,    #    caché auto-aprendido (web previa)
        busqueda_legislacion_educativa,      # 3) BOE, BOJA, Junta de Andalucía (web)
        tool_busqueda_general,               #    fallback internet abierto
        extraer_contenido_web,               #    leer el texto completo de una ley
    ]


async def obtener_todas_las_tools(perfil: str = "alumnos") -> list:
    """Compatibilidad con código existente."""
    if perfil == "profesores":
        return await obtener_tools_profesorado()
    return await obtener_tools_publicas()
