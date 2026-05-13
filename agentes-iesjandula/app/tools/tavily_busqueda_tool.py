import os
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

api_key = os.getenv("TAVILY_API_KEY")
client = None

if api_key is None:
    print("⚠️ No se encontró TAVILY_API_KEY en el archivo .env")
else:
    client = TavilyClient(api_key=api_key)

from langchain_core.tools import tool

# Dominios oficiales para búsqueda restringida
DOMINIOS_IES = [
    "blogsaverroes.juntadeandalucia.es/iesjandula/",
    "fp.iesjandula.es",
    "iesjandula.es",
    "www.iesjandula.es"
]

@tool
def busqueda_web_ies_jandula(search: str) -> str:
    """Busca información EXHAUSTIVA en la web oficial del IES Jándula y sitios relacionados.
    USA ESTA HERRAMIENTA para: noticias, actividades, FP, secretaría, plazos y cualquier 
    dato público del centro.
    Esta herramienta realiza una búsqueda profunda (advanced) y analiza múltiples fuentes."""
    
    if not client:
        return "Error: TAVILY_API_KEY no configurada."

    print(f"\n🌐 [TOOL: busqueda_web_ies_jandula] Búsqueda exhaustiva: {search}")
    
    try:
        # 1. Intento inicial restringido a dominios del centro
        print(f"   🔍 Buscando en dominios del centro...")
        response = client.search(
            query=search,
            search_depth="advanced",
            max_results=8,
            include_domains=DOMINIOS_IES
        )
        
        # Si no hay resultados o son muy pocos, hacemos fallback a búsqueda general filtrada
        if not response.get("results") or len(response["results"]) < 2:
            print(f"   ⚠️ Pocos resultados en dominios oficiales. Ampliando búsqueda...")
            query_ampliada = f"{search} IES Jándula Andújar"
            response = client.search(
                query=query_ampliada,
                search_depth="advanced",
                max_results=10
            )
        
        # Formatear resultados para el LLM
        contexto = []
        for res in response.get("results", []):
            contexto.append(f"FUENTE: {res['url']}\nTÍTULO: {res['title']}\nCONTENIDO: {res['content']}\n")
        
        if not contexto:
            return "No se encontró información relevante tras una búsqueda exhaustiva."
            
        print(f"   ✅ [TOOL] Éxito: {len(contexto)} fuentes encontradas.")
        return "\n---\n".join(contexto)

    except Exception as e:
        print(f"   ❌ Error en búsqueda exhaustiva: {e}")
        return f"Error al realizar la búsqueda: {e}"

@tool
def busqueda_web_general(search: str) -> str:
    """Busca información GENERAL en todo internet con profundidad avanzada.
    USA ESTA HERRAMIENTA para: normativa educativa (LOMLOE, Junta de Andalucía), 
    legislación, Séneca, iPasen y temas educativos globales."""
    
    if not client:
        return "Error: TAVILY_API_KEY no configurada."

    print(f"\n🌍 [TOOL: busqueda_web_general] Búsqueda profunda: {search}")
    
    try:
        response = client.search(
            query=search,
            search_depth="advanced",
            max_results=8
        )
        
        contexto = []
        for res in response.get("results", []):
            contexto.append(f"FUENTE: {res['url']}\nTÍTULO: {res['title']}\nCONTENIDO: {res['content']}\n")
            
        return "\n---\n".join(contexto)
    except Exception as e:
        return f"Error en búsqueda general: {e}"

# Exportamos las funciones
tool_busqueda_web_centro = busqueda_web_ies_jandula
tool_busqueda_general = busqueda_web_general