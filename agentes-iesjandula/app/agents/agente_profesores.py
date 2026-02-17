import os
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import tools_condition
from langchain_ollama import ChatOllama
from langchain_core.messages import ToolMessage

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
    SYSTEM_PROMPT = """Eres el Asistente Oficial del IES Jándula (Andújar). 
        Tu ámbito de actuación es EXCLUSIVAMENTE el centro educativo IES Jándula.
        Respondes SIEMPRE en español mientras no te pidan que respondas en otro idioma.

        PRIORIDAD DE BÚSQUEDA:
        1. Información Interna: Usa 'guia_profesorado' para datos sobre profesores, guía de actuación, orientación de profesorado... o navega en la
            Web Oficial: Para noticias, contacto, calendarios y eventos, oferta de módulos, blogs, oferta educativa navega en https://blogsaverroes.juntadeandalucia.es/iesjandula/ usando Playwright.
        2. Internet (Tavily): Úsalo ÚNICAMENTE si el usuario pregunta algo general necesario para entender un concepto del centro, o si buscas una noticia externa que mencione específicamente al 'IES Jándula'.

        REGLA CRÍTICA: 
        - No des consejos generales de educación en Andalucía a menos que estén publicados en la web del centro. 
        - Si la información no es específica del IES Jándula, responde: "Esa información no consta en los registros oficiales del IES Jándula".
        - Responde siempre de forma concisa y en español.
        """
    
    chat = ChatOllama(model="gpt-oss:20b-cloud", temperature=0)
    llm_con_herramientas = chat.bind_tools(herramientas)
    
    # Crear mapa de herramientas para búsqueda rápida
    tool_map = {tool.name: tool for tool in herramientas}

    # 3. Definición de Nodos
    def chatbot(estado: Estado):
        # Es vital pasar el SystemPrompt en la lista de mensajes o en la configuración
        return {"messages": [llm_con_herramientas.invoke(estado["messages"])]}

    def ejecutar_tools_sync(estado: Estado):
        """
        Ejecuta tools de forma sincrónica en el mismo thread.
        Evita ThreadPoolExecutor de ToolNode que causa conflictos con Playwright.
        """
        messages = estado["messages"]
        if not messages:
            return {"messages": []}
        
        last_message = messages[-1]
        
        # Verificar si el último mensaje tiene tool_calls
        if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
            return {"messages": []}
        
        # Ejecutar cada tool secuencialmente
        tool_results = []
        for tool_call in last_message.tool_calls:
            tool_name = tool_call.get("name") if isinstance(tool_call, dict) else tool_call.name
            tool_input = tool_call.get("args") if isinstance(tool_call, dict) else tool_call.args
            
            if tool_name not in tool_map:
                result = f"Error: tool '{tool_name}' no encontrada"
            else:
                try:
                    tool = tool_map[tool_name]
                    result = tool.invoke(tool_input)
                except Exception as e:
                    result = f"Error ejecutando {tool_name}: {str(e)}"
            
            # Crear mensaje de respuesta de la tool
            tool_message = ToolMessage(
                content=str(result),
                tool_call_id=tool_call.get("id") if isinstance(tool_call, dict) else tool_call.id,
                name=tool_name
            )
            tool_results.append(tool_message)
        
        return {"messages": tool_results}

    # 4. Construcción del Grafo
    constructor = StateGraph(Estado)
    constructor.add_node("chatbot", chatbot)
    constructor.add_node("tools", ejecutar_tools_sync)
    
    constructor.add_conditional_edges("chatbot", tools_condition)
    constructor.add_edge("tools", "chatbot")
    constructor.add_edge(START, "chatbot")

    memoria = MemorySaver()
    return constructor.compile(checkpointer=memoria)