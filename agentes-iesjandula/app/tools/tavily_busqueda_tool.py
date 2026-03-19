import os
from dotenv import load_dotenv
from langchain_tavily import TavilySearch

load_dotenv()

api_key = os.getenv("TAVILY_API_KEY")

if api_key is None:
    print("⚠️ No se encontró TAVILY_API_KEY en el archivo .env")
else:
    os.environ["TAVILY_API_KEY"] = api_key

# max_results=3 es suficiente — más resultados no mejoran la respuesta
# y aumentan el contexto innecesariamente con Ollama local
tool_busqueda_general = TavilySearch(
    max_results=3,
    tavily_api_key=api_key,
    description=(
        "Busca información en internet sobre temas generales "
        "no cubiertos por las guías internas del IES Jándula. "
        "Útil para normativa educativa externa (Junta de Andalucía, BOE), "
        "noticias del sector educativo o consultas que no son específicas del centro. "
        "NO usar para información interna del IES Jándula."
    )
)