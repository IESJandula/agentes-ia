"""
AgentConfig.py — IES Jándula
Grafo LangGraph con routing por perfil (alumnos / profesores).
"""

from __future__ import annotations

from typing import Annotated, Literal
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage

from app.tools import obtener_tools_publicas, obtener_tools_profesorado
from .prompts.prompt_manager import PROMPTS, BEHAVIOR_PUBLIC, BEHAVIOR_TEACHER, REGLAS_VOZ


# ─────────────────────────────────────────────────────────────────────────────
# Estado
# ─────────────────────────────────────────────────────────────────────────────

class Estado(TypedDict):
    messages:      Annotated[list, add_messages]
    tipo_consulta: Literal["publica", "profesorado"] | None


# ─────────────────────────────────────────────────────────────────────────────
# Construcción del grafo
# ─────────────────────────────────────────────────────────────────────────────

async def configurar_grafo_ies(perfil: str, es_voz: bool = False):

    # ── 1. Tools por fuente ──────────────────────────────────────────────────
    tools_pub  = await obtener_tools_publicas()
    tools_prof = await obtener_tools_profesorado() if perfil == "profesores" else []

    map_pub  = {t.name: t for t in tools_pub}
    map_prof = {t.name: t for t in tools_prof}
    map_todo = {**map_pub, **map_prof}

    # ── 2. Prompts ───────────────────────────────────────────────────────────
    _voz_suffix  = REGLAS_VOZ if es_voz else ""
    PROMPT_PUB  = PROMPTS[perfil] + "\n\n" + BEHAVIOR_PUBLIC  + _voz_suffix
    PROMPT_PROF = PROMPTS[perfil] + "\n\n" + BEHAVIOR_TEACHER + _voz_suffix

    # ── 3. LLMs ─────────────────────────────────────────────────────────────
    _base_llm  = ChatOllama(model="llama3.1:8b", temperature=0.4)
    llm_clasif = _base_llm                                      # sin tools
    llm_pub    = _base_llm.bind_tools(tools_pub)
    llm_prof   = _base_llm.bind_tools(tools_prof) if tools_prof else _base_llm

    # ─────────────────────────────────────────────────────────────────────────
    # Nodos
    # ─────────────────────────────────────────────────────────────────────────

    # ── Helper: reconstruir contexto de ToolMessages ─────────────────────────
    def _build_tool_context(estado: Estado) -> str:
        """Extrae los ToolMessages del turno actual y los formatea como contexto."""
        contexto = ""
        for msg in reversed(estado["messages"]):
            if isinstance(msg, ToolMessage):
                contexto = f"\n\nCONTEXTO DE TOOL ({msg.name}):\n{msg.content}" + contexto
            elif getattr(msg, "tool_calls", None):
                break  # Detenerse en el AI message que inició las llamadas
        if contexto:
            contexto = f"\n\n=== INFORMACIÓN RECUPERADA ==={contexto}\n\nUsa esta información para responder con precisión."
        return contexto

    # ── Clasificador ─────────────────────────────────────────────────────────
    async def clasificar(estado: Estado) -> dict:
        """Decide si la consulta es pública o interna de profesorado."""
        if perfil != "profesores" or not tools_prof:
            return {"tipo_consulta": "publica"}

        ultimo = estado["messages"][-1]
        texto  = ultimo.content if hasattr(ultimo, "content") else str(ultimo)

        sys_clasificador = SystemMessage(content="""Eres el router del asistente del IES Jándula.
Clasifica la consulta del usuario en UNA sola palabra:

  profesorado → planes (acogida, de centro, igualdad), protocolos (incendio, accidentes, evacuación), 
                normativa interna (NOF, PEC, PGA, ROF, ROFE), CCP, actas, evaluaciones internas,
                reuniones de departamento, protocolo docente, nombres de profesores o cargos directivos.

  publica     → noticias, eventos, actividades extraescolares, horarios generales,
                información para familias o alumnos, transporte, comedor, becas, matrículas.

Responde ÚNICAMENTE con la palabra: profesorado o publica.
Si el perfil del usuario es PROFESOR y la consulta trata sobre planes o protocolos del centro, elige: profesorado.
Ante la duda responde: profesorado""")

        respuesta = await llm_clasif.ainvoke([sys_clasificador, HumanMessage(content=texto)])
        raw = respuesta.content.strip().lower()

        tipo: Literal["publica", "profesorado"] = (
            "profesorado" if any(x in raw for x in ["profesor", "docente", "interna"]) else "publica"
        )
        print(f"🔀 Clasificador → {tipo}  (raw: '{raw}')")
        return {"tipo_consulta": tipo}

    # ── Chatbot público ───────────────────────────────────────────────────────
    async def chatbot_publico(estado: Estado) -> dict:
        # Poda de historial: mantenemos los últimos 10 mensajes para no saturar al modelo
        mensajes = estado["messages"]
        if len(mensajes) > 10:
            mensajes = mensajes[-10:]
            
        system = SystemMessage(content=PROMPT_PUB + _build_tool_context(estado))
        respuesta = await llm_pub.ainvoke([system] + mensajes)
        return {"messages": [respuesta]}

    # ── Chatbot profesorado ───────────────────────────────────────────────────
    async def chatbot_profesorado(estado: Estado) -> dict:
        # Poda de historial
        mensajes = estado["messages"]
        if len(mensajes) > 10:
            mensajes = mensajes[-10:]

        system = SystemMessage(content=PROMPT_PROF + _build_tool_context(estado))
        respuesta = await llm_prof.ainvoke([system] + mensajes)
        return {"messages": [respuesta]}

    # ── Ejecutor de tools ─────────────────────────────────────────────────────
    async def ejecutar_tools(estado: Estado) -> dict:
        ultimo  = estado["messages"][-1]
        tipo    = estado.get("tipo_consulta", "publica")
        mapa    = map_prof if tipo == "profesorado" else map_pub

        results = []
        for call in ultimo.tool_calls:
            nombre = call["name"]
            try:
                if nombre not in mapa:
                    # Guardrail: tool fuera de la rama activa
                    obs = (
                        f"⚠️ La herramienta '{nombre}' no está disponible "
                        f"en la rama '{tipo}'. Usa solo las herramientas permitidas."
                    )
                else:
                    obs = await mapa[nombre].ainvoke(call["args"])
            except Exception as e:
                obs = f"Error en herramienta '{nombre}': {e}"

            results.append(ToolMessage(
                content=str(obs),
                tool_call_id=call["id"],
                name=nombre,
            ))
        return {"messages": results}

    # ─────────────────────────────────────────────────────────────────────────
    # Routing
    # ─────────────────────────────────────────────────────────────────────────

    def _hay_tool_calls(estado: Estado) -> bool:
        ultimo = estado["messages"][-1]
        return bool(getattr(ultimo, "tool_calls", None))

    def route_tras_clasificar(estado: Estado) -> str:
        return estado.get("tipo_consulta", "publica")

    def route_chatbot_publico(estado: Estado) -> str:
        return "tools" if _hay_tool_calls(estado) else END

    def route_chatbot_profesorado(estado: Estado) -> str:
        return "tools" if _hay_tool_calls(estado) else END

    def route_tras_tools(estado: Estado) -> str:
        """Vuelve al chatbot correcto según la rama activa."""
        return estado.get("tipo_consulta", "publica")

    # ─────────────────────────────────────────────────────────────────────────
    # Construcción
    # ─────────────────────────────────────────────────────────────────────────

    builder = StateGraph(Estado)

    builder.add_node("clasificar",           clasificar)
    builder.add_node("chatbot_publico",      chatbot_publico)
    builder.add_node("chatbot_profesorado",  chatbot_profesorado)
    builder.add_node("tools",                ejecutar_tools)

    builder.add_edge(START, "clasificar")

    builder.add_conditional_edges(
        "clasificar",
        route_tras_clasificar,
        {
            "publica":      "chatbot_publico",
            "profesorado":  "chatbot_profesorado",
        },
    )

    builder.add_conditional_edges(
        "chatbot_publico",
        route_chatbot_publico,
        {"tools": "tools", END: END},
    )

    builder.add_conditional_edges(
        "chatbot_profesorado",
        route_chatbot_profesorado,
        {"tools": "tools", END: END},
    )

    builder.add_conditional_edges(
        "tools",
        route_tras_tools,
        {
            "publica":      "chatbot_publico",
            "profesorado":  "chatbot_profesorado",
        },
    )

    grafo = builder.compile(checkpointer=MemorySaver())
    # recursion_limit reducido: 15 ciclos son más que suficientes
    # y protegen contra bucles infinitos de tool-calling

    # ── Imagen del grafo ─────────────────────────────────────────────────────
    _guardar_imagen_grafo(grafo)

    return grafo


# ─────────────────────────────────────────────────────────────────────────────
# Utilidad: guardar imagen del grafo
# ─────────────────────────────────────────────────────────────────────────────

def _guardar_imagen_grafo(grafo, ruta: str = "grafo_ies_jandula.png") -> None:
    """
    Guarda una imagen PNG del grafo en el directorio raíz del proyecto.
    Requiere: pip install grandalf   (o bien playwright instalado para Mermaid)

    Si falla silenciosamente imprime el Mermaid como fallback en consola.
    """
    try:
        png = grafo.get_graph().draw_mermaid_png()
        with open(ruta, "wb") as f:
            f.write(png)
        print(f"✅ Imagen del grafo guardada en: {ruta}")
    except Exception as e:
        print(f"⚠️  No se pudo generar la imagen PNG: {e}")
        print("   Instala 'grandalf' con:  pip install grandalf")
        print("   O visualiza el grafo en: https://mermaid.live")
        print("\n── Mermaid del grafo ──────────────────────────────")
        try:
            print(grafo.get_graph().draw_mermaid())
        except Exception:
            pass
        print("───────────────────────────────────────────────────\n")