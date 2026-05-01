from langchain_core.tools import tool

@tool
def dar_respuesta_final(respuesta: str):
    """Usa esta herramienta cuando tengas la información necesaria para responder al usuario y quieras finalizar la sesión."""
    print(f"\n🏁 [TOOL: dar_respuesta_final] Respuesta: {respuesta[:100]}...")
    return respuesta