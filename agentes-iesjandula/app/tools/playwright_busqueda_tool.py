from playwright.async_api import async_playwright
from langchain_community.agent_toolkits import PlayWrightBrowserToolkit


async def get_playwright_tools():
    """
    Inicializa el navegador Playwright y devuelve las tools de navegación.
    Estas tools están pensadas EXCLUSIVAMENTE para consultar la web pública
    del IES Jándula (blog Averroes) y páginas externas de interés general.

    NO se deben usar para acceder a documentos internos del profesorado.
    """
    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=True)
        toolkit = PlayWrightBrowserToolkit.from_browser(async_browser=browser)
        tools = toolkit.get_tools()

        # Sobreescribimos la descripción de las tools de Playwright
        # para que el LLM sepa exactamente para qué sirven
        """ for t in tools:
            t.description = (
                f"{t.description} "
                "USAR SOLO para navegar la web pública del IES Jándula: https://blogsaverroes.juntadeandalucia.es/iesjandula/ "
                "(blog Averroes, noticias, eventos, horarios generales) "
                "o páginas web externas. "
                "NO usar para documentos internos ni guía del profesorado."
            ) """

        return tools
    except Exception as e:
        print(f"⚠️ No se pudieron cargar las herramientas de Playwright: {e}")
        return []