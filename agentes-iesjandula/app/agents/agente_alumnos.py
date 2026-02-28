from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import tools_condition
from langchain_ollama import ChatOllama
from .agente_profesores import Estado, ejecutar_tools_sync # Reutilizamos lógica
from tools import obtener_todas_las_tools

async def inicializar_agente_alumnos(es_voz=False):
    """
    Crea el grafo específico para el Agente de Alumnos.
    """
    # 1. Cargamos las herramientas filtradas para ALUMNOS
    herramientas = await obtener_todas_las_tools(perfil="alumnos")
    
    SYSTEM_PROMPT = """Eres el Asistente Oficial para ALUMNOS del IES Jándula.
        Tu objetivo es ayudar a los estudiantes con dudas sobre el centro.
        
        PRIORIDAD DE BÚSQUEDA:
        1. Información Interna: Usa 'guia_alumnado' para fechas de exámenes, normas de convivencia, actividades extraescolares y servicios del centro.
        2. Web Oficial: Navega para ver el menú del comedor, noticias del tablón o eventos.
        ... (resto del prompt igual que profesores pero enfocado a alumnos)
    """

    if es_voz:
        SYSTEM_PROMPT += " (Instrucciones de modo voz...)"

    chat = ChatOllama(model="gpt-oss:20b-cloud", temperature=0)
    llm_con_herramientas = chat.bind_tools(herramientas)
    
    # Reutilizamos el mapa de herramientas para el nodo de ejecución
    tool_map = {tool.name: tool for tool in herramientas}

    # Definimos el nodo chatbot localmente para usar su SYSTEM_PROMPT específico
    def chatbot(estado: Estado):
        return {"messages": [llm_con_herramientas.invoke([{"role": "system", "content": SYSTEM_PROMPT}] + estado["messages"])]}

    # Construcción del grafo (Misma estructura)
    constructor = StateGraph(Estado)
    constructor.add_node("chatbot", chatbot)
    constructor.add_node("tools", ejecutar_tools_sync) 
    
    constructor.add_conditional_edges("chatbot", tools_condition)
    constructor.add_edge("tools", "chatbot")
    constructor.add_edge(START, "chatbot")

    return constructor.compile(checkpointer=MemorySaver())