from playwright.async_api import async_playwright
from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
from langchain_core.tools import tool
from bs4 import BeautifulSoup


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

@tool
async def extraer_contenido_web(url: str) -> str:
    """Extrae TODO el texto de una URL específica.
    USA ESTA HERRAMIENTA cuando encuentres un enlace prometedor en la búsqueda 
    pero el resumen (snippet) no sea suficiente para responder a la pregunta.
    Ideal para: ver planes de estudios, leer noticias completas o detalles de ciclos."""
    
    print(f"\n🕷️  [SCRAPER] Navegando a: {url}...")
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # Navegar con timeout y esperar a que la red esté inactiva
            await page.goto(url, timeout=30000, wait_until="networkidle")
            
            # Obtener el HTML y limpiar con BeautifulSoup
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # Eliminar scripts, estilos y menús de navegación comunes para limpiar el texto
            for element in soup(['script', 'style', 'nav', 'footer', 'header']):
                element.decompose()
            
            texto = soup.get_text(separator=' ', strip=True)
            
            await browser.close()
            
            # Limitar a los primeros 10,000 caracteres para no saturar el contexto
            resultado = texto[:10000]
            print(f"   ✅ [SCRAPER] Contenido extraído ({len(resultado)} caracteres).")
            return resultado
            
    except Exception as e:
        print(f"   ❌ [SCRAPER] Error navegando a {url}: {e}")
        return f"No se pudo extraer el contenido de la web: {e}"

# Función para obtener las herramientas de este módulo
def obtener_herramientas_scraping():
    return [extraer_contenido_web]