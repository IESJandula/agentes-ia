import os
from dotenv import load_dotenv
from langchain_tavily import TavilySearch

load_dotenv()

# Obtenemos la clave
api_key = os.getenv("TAVILY_API_KEY")

# Verificamos si la clave existe antes de intentar asignarla
if api_key is None:
    print("⚠️ Error: No se encontró TAVILY_API_KEY en el archivo .env")
    # Opcional: puedes poner la clave a mano aquí temporalmente para probar
    # api_key = "tvly-tu_clave_real" 
else:
    os.environ["TAVILY_API_KEY"] = api_key

tool_busqueda_general = TavilySearch(
        max_results=3, 
        tavily_api_key=api_key
    )