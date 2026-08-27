from .guia_profesorado_tool import guia_profesorado
from .guia_alumnado_tool import guia_alumnado
from .tavily_busqueda_tool import tool_busqueda_web_centro, tool_busqueda_general
from .playwright_busqueda_tool import extraer_contenido_web
from .legislacion_tool import busqueda_legislacion_educativa
from .legislacion_local_tool import consultar_legislacion
from .centro_tool import consultar_info_centro
from .conocimiento_tool import consultar_conocimiento_aprendido

#: Categoría de la base de conocimiento → tool que la consulta.
#: El ORDEN en que se le presentan las tools al modelo es la prioridad de
#: fuentes, y lo decide el panel de administración (KbService.orden()), no una
#: lista escrita a mano aquí. Las tools de web van siempre después: son el
#: último recurso, por debajo de cualquier documento indexado del centro.
TOOL_POR_CATEGORIA = {
    "centro": consultar_info_centro,
    "profesores": guia_profesorado,
    "alumnos": guia_alumnado,
    "legislacion": consultar_legislacion,
    "conocimiento": consultar_conocimiento_aprendido,
}

#: Tools de búsqueda documental que NO tiene sentido ofrecer a cada perfil.
#: La guía del profesorado es normativa interna: no se le pasa al perfil de
#: alumnado ni aunque el orden de categorías la ponga la primera.
CATEGORIAS_INTERNAS = {"profesores"}


def _tools_documentales(incluir_internas: bool) -> list:
    """Tools de consulta documental, en el orden configurado en el panel.

    El import de KbService va DENTRO de la función, no arriba: `app.api.services`
    acaba importando `app.agents`, que importa este mismo módulo. Con el import
    a nivel de módulo, quien importara `app.tools` antes que `app.api.services`
    cerraría el ciclo y reventaría el arranque; así solo se resuelve cuando ya
    están los dos cargados.
    """
    from app.api.services.KbService import kb_service

    tools = []
    for categoria in kb_service.orden():
        if categoria in CATEGORIAS_INTERNAS and not incluir_internas:
            continue
        tool = TOOL_POR_CATEGORIA.get(categoria)
        if tool is not None:
            tools.append(tool)
    return tools


async def obtener_tools_publicas() -> list:
    """
    Tools para el perfil de alumnado: documentación no interna + web.
    """
    return [
        *_tools_documentales(incluir_internas=False),
        tool_busqueda_web_centro,           # web del centro (último recurso)
        tool_busqueda_general,
        extraer_contenido_web,
    ]


async def obtener_tools_profesorado() -> list:
    """
    Tools para profesores: toda la documentación indexada, y la web al final.
    """
    return [
        *_tools_documentales(incluir_internas=True),
        tool_busqueda_web_centro,           # web (último recurso)
        tool_busqueda_general,
        extraer_contenido_web,
    ]


async def obtener_tools_legislacion() -> list:
    """
    Tools especializadas para consultas legislativas y normativas.

    Aquí el orden NO sale del panel: sea cual sea la prioridad general, en una
    pregunta legislativa la legislación oficial indexada va primero. El panel
    ordena las fuentes de uso general, no anula una especialización.
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
