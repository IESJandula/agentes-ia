from playwright.sync_api import sync_playwright
from langchain_community.agent_toolkits import PlayWrightBrowserToolkit

def get_playwright_tools():
    # 1. Iniciamos el navegador
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    toolkit = PlayWrightBrowserToolkit(sync_browser=browser)
    tools = toolkit.get_tools()
    return tools