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

async def inicializar_agente_profesores(es_voz=False):
    """
    Crea el grafo específico para el Agente de Profesores.
    """
    # 1. Cargamos todas las herramientas desde la carpeta tools
    herramientas = await obtener_todas_las_tools()
    
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
    if es_voz:
        SYSTEM_PROMPT += """
        MODO VOZ ACTIVO: Responde SIEMPRE en un solo párrafo corto (máximo 3 frases). 
        PROHIBIDO usar tablas, listas, asteriscos, negritas o cualquier signo de Markdown. 
        Escribe los números con palabras si es necesario para que suenen naturales."""

    chat = ChatOllama(model="gpt-oss:20b-cloud", temperature=0)
    llm_con_herramientas = chat.bind_tools(herramientas)
    
    # Crear mapa de herramientas para búsqueda rápida
    tool_map = {tool.name: tool for tool in herramientas}

    # 3. Definición de Nodos
    def chatbot(estado: Estado):
        # Es vital pasar el SystemPrompt en la lista de mensajes o en la configuración
        system_message = {"role": "system", "content": SYSTEM_PROMPT}
        return {"messages": [llm_con_herramientas.invoke(estado["messages"])]}

    async def ejecutar_tools_async(estado: Estado):
        """
        Versión asíncrona para manejar Playwright y las herramientas de RAG.
        """
        ultimo_mensaje = estado["messages"][-1]
        tool_results = []
        
        for tool_call in ultimo_mensaje.tool_calls:
            tool_name = tool_call["name"]
            tool_input = tool_call["args"]
            
            # Invocación asíncrona de la herramienta
            observacion = await tool_map[tool_name].ainvoke(tool_input)
            
            tool_results.append(ToolMessage(
                content=str(observacion),
                tool_call_id=tool_call["id"],
                name=tool_name
            ))
        
        return {"messages": tool_results}

    # 4. Construcción del Grafo
    constructor = StateGraph(Estado)
    constructor.add_node("chatbot", chatbot)
    constructor.add_node("tools", ejecutar_tools_async)
    
    constructor.add_conditional_edges("chatbot", tools_condition)
    constructor.add_edge("tools", "chatbot")
    constructor.add_edge(START, "chatbot")

    memoria = MemorySaver()
    return constructor.compile(checkpointer=memoria)