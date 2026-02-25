from playwright.async_api import async_playwright
from langchain_community.agent_toolkits import PlayWrightBrowserToolkit

async def get_playwright_tools():
    # 1. Iniciamos el navegador
    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=True)
        toolkit = PlayWrightBrowserToolkit.from_browser(async_browser=browser)
        tools = toolkit.get_tools()
        return tools
    except Exception as e:
        print("No se puedo cargar las herramientas de playWright jeje")
        return[]