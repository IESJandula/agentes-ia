import os
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import tools_condition
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import ToolNode

# IMPORTACIONES DE TU NUEVA ESTRUCTURA
from app.tools import obtener_todas_las_tools

class Estado(TypedDict):
    messages: Annotated[list, add_messages]

def inicializar_agente_profesores():
    """
    Crea el grafo específico para el Agente de Profesores.
    """
    # 1. Cargamos todas las herramientas desde la carpeta tools
    herramientas = obtener_todas_las_tools()
    
    # 2. Configuración del LLM
    SYSTEM_PROMPT = """Eres el Asistente Oficial del IES Jándula orientado a PROFESORES.
    Prioridad: 1. Guía profesorado (PDF), 2. Web Jándula (Playwright), 3. Internet."""
    
    chat = ChatOllama(model="gpt-oss:20b-cloud", temperature=0)
    llm_con_herramientas = chat.bind_tools(herramientas)

    # 3. Definición de Nodos
    def chatbot(estado: Estado):
        # Es vital pasar el SystemPrompt en la lista de mensajes o en la configuración
        return {"messages": [llm_con_herramientas.invoke(estado["messages"])]}

    node_tools = ToolNode(herramientas)

    # 4. Construcción del Grafo
    constructor = StateGraph(Estado)
    constructor.add_node("chatbot", chatbot)
    constructor.add_node("tools", node_tools)
    
    constructor.add_conditional_edges("chatbot", tools_condition)
    constructor.add_edge("tools", "chatbot")
    constructor.add_edge(START, "chatbot")

    memoria = MemorySaver()
    return constructor.compile(checkpointer=memoria)