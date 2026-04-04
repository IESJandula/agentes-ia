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
        "Busca información en internet sobre temas generales o información de la web pública de IES Jándula. "
        "Si buscas información sobre el IES Jándula (ej: secretaría, horarios, matrículas, noticias del centro), "
        "PRIORIZA buscar en su web oficial añadiendo 'site:blogsaverroes.juntadeandalucia.es/iesjandula' a tu consulta. "
        "También puedes buscar en webs oficiales de la Junta de Andalucía u otras si es necesario para normativa externa. "
        "NO uses esto para consultas internas confidenciales de profesores."
    )
)