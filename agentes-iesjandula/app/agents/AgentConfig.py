from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import tools_condition
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, ToolMessage
from app.tools import obtener_todas_las_tools
from .prompts.prompt_manager import PROMPTS, REGLAS_VOZ

class Estado(TypedDict):
    messages: Annotated[list, add_messages]

async def configurar_grafo_ies(perfil: str, es_voz: bool = False):
    
    herramientas = await obtener_todas_las_tools(perfil=perfil)
    tool_map = {tool.name: tool for tool in herramientas}
    
    prompt_base = PROMPTS.get(perfil, PROMPTS["alumnos"])
    if es_voz:
        prompt_base += REGLAS_VOZ

    llm = ChatOllama(model="gpt-oss:20b-cloud", temperature=0).bind_tools(herramientas)

    def chatbot(estado: Estado):
        return {"messages": [llm.invoke([SystemMessage(content=prompt_base)] + estado["messages"])]}

    async def ejecutar_tools(estado: Estado):
        ultimo_mensaje = estado["messages"][-1]
        results = []
        for call in ultimo_mensaje.tool_calls:
            try:
                obs = await tool_map[call["name"]].ainvoke(call["args"])
            except Exception as e:
                obs = f"Error en herramienta: {e}"
            results.append(ToolMessage(content=str(obs), tool_call_id=call["id"], name=call["name"]))
        return {"messages": results}

    # 4. Construcción
    builder = StateGraph(Estado)
    builder.add_node("chatbot", chatbot)
    builder.add_node("tools", ejecutar_tools)
    builder.add_conditional_edges("chatbot", tools_condition)
    builder.add_edge("tools", "chatbot")
    builder.add_edge(START, "chatbot")
    
    return builder.compile(checkpointer=MemorySaver())