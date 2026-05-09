"""
AgentConfig.py — IES Jándula
Grafo LangGraph con routing por perfil (alumnos / profesores).
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Annotated, Literal
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage, ToolMessage
import os


# ─────────────────────────────────────────────────────────────────────────────
# Helper: retry con backoff para rate-limit 429 de Gemini (free tier: 5 rpm)
# ─────────────────────────────────────────────────────────────────────────────

async def _llm_invoke_con_retry(llm, mensajes, max_intentos: int = 4, espera_base: float = 20.0):
    """
    Llama a llm.ainvoke(mensajes) con reintentos automáticos ante 429 RESOURCE_EXHAUSTED.

    Distingue dos tipos de límite:
    - PerMinute → reintenta con backoff exponencial (espera_base * 2^i)
    - PerDay    → falla inmediatamente con mensaje claro (reintentar en segundos no sirve)
    """
    import re as _re
    for intento in range(1, max_intentos + 1):
        try:
            return await llm.ainvoke(mensajes)
        except Exception as e:
            err = str(e)
            es_rate_limit = "429" in err or "RESOURCE_EXHAUSTED" in err

            if not es_rate_limit:
                raise  # error diferente al rate-limit

            # ¿Es cuota diaria? No tiene sentido reintentar.
            if "PerDay" in err or "per_day" in err.lower():
                m = _re.search(r"model['\"]?\s*[:\s]+['\"]?([a-z0-9._-]+)", err)
                modelo = m.group(1) if m else "desconocido"
                raise RuntimeError(
                    f"⛔ Cuota DIARIA agotada para el modelo '{modelo}'.\n"
                    "El servicio estará disponible mañana (UTC 00:00).\n"
                    "Considera activar facturación en https://ai.dev/rate-limit"
                ) from e

            # Cuota por minuto → reintentar con backoff
            if intento < max_intentos:
                wait = espera_base * (2 ** (intento - 1))
                print(f"   ⏳ [LLM Rate-limit/min] Intento {intento}/{max_intentos}. Esperando {wait:.0f}s...")
                await asyncio.sleep(wait)
            else:
                raise  # agotados los reintentos

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
    # Modelo configurable por variable de entorno para facilitar el cambio.
    # Opciones recomendadas (AI Studio free tier, de menor a mayor cuota):
    #   gemini-3-flash-preview  →  20 req/día  (evitar)
    #   gemini-2.0-flash-lite   →  200 req/día
    #   gemini-1.5-flash        →  1500 req/día ← recomendado para desarrollo
    if not os.getenv("GOOGLE_API_KEY"):
        raise ValueError("⚠️ GOOGLE_API_KEY no está configurada en las variables de entorno")

    _model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    print(f"   🤖 Usando modelo LLM: {_model_name}")
    _base_llm  = ChatGoogleGenerativeAI(
        model=_model_name,
        temperature=0.4,
        max_retries=3,
    )
    llm_clasif = _base_llm                                      # sin tools
    llm_pub    = _base_llm.bind_tools(tools_pub) if tools_pub else _base_llm
    llm_prof   = _base_llm.bind_tools(tools_prof) if tools_prof else _base_llm

    # ─────────────────────────────────────────────────────────────────────────
    # Nodos
    # ─────────────────────────────────────────────────────────────────────────

    def _extract_text(content) -> str:
        """Extrae el texto de un objeto content que puede ser str o list (multimodal)."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return " ".join(
                part.get("text", "") if isinstance(part, dict) else str(part) 
                for part in content
            )
        return str(content)

    # ── Helper: detectar saludos simples ───────────────────────────────────
    _SALUDOS = [
        "hola", "buenos días", "buenas tardes", "buenas noches",
        "gracias", "muchas gracias", "adiós", "hasta luego",
        "bye", "ok", "vale", "de acuerdo", "entendido",
    ]

    def _es_saludo(texto: str) -> bool:
        """Detecta si el texto es un saludo o respuesta simple que no requiere tool."""
        if not texto: return False
        limpio = texto.strip().lower().rstrip(".,!?¿¡")
        # Coincidencia exacta o inicio de saludo
        return any(limpio == s or limpio.startswith(s + " ") for s in _SALUDOS) and len(limpio) < 40

    # ── Helper: obtener último mensaje del usuario ────────────────────────────
    def _ultimo_mensaje_usuario(estado: Estado) -> str | None:
        for m in reversed(estado["messages"]):
            if isinstance(m, HumanMessage):
                return _extract_text(m.content)
        return None

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
            contexto = f"\n\n=== INFORMACIÓN RECUPERADA (USA ESTO PARA RESPONDER) ==={contexto}\n\nINSTRUCCIÓN: Responde a la pregunta del usuario utilizando ÚNICAMENTE la información anterior. Si la información no es suficiente, indícalo."
        return contexto

    # ── Clasificador ─────────────────────────────────────────────────────────
    async def clasificar(estado: Estado) -> dict:
        """Decide si la consulta es pública o interna de profesorado."""
        if perfil != "profesores" or not tools_prof:
            return {"tipo_consulta": "publica"}

        ultimo = estado["messages"][-1]
        texto  = ultimo.content if hasattr(ultimo, "content") else str(ultimo)

        sys_clasificador = SystemMessage(content="""Eres un sistema de enrutamiento estricto para el IES Jándula.
Tu ÚNICA función es clasificar la consulta del usuario en una de estas dos categorías.

CATEGORÍA 'profesorado' (información INTERNA del centro):
- Nombres ESPECÍFICOS de profesores, tutores o jefes de departamento (ej: "¿quién es Juan García?").
- Cargos del EQUIPO DIRECTIVO: directora, jefe de estudios, secretario/a (ej: "¿quién es la directora?").
- Documentación interna: planes (acogida, igualdad), protocolos (incendio, accidentes), normativa interna (NOF, PEC, ROF, actas).
- Gestión docente: guardias, Séneca, partes de incidencias, sustituciones, reuniones de departamento, horarios de profesores.

CATEGORÍA 'publica' (información accesible en la web del centro):
- TODO sobre ciclos formativos, FP, grados superiores/medios, ESO, Bachillerato (descripción, asignaturas, requisitos, salidas profesionales).
- Ejemplos: "ciclo de desarrollo de aplicaciones web", "CFGS DAW", "FP de informática", "grado medio de gestión administrativa".
- Noticias, eventos, calendario escolar, actividades extraescolares, clubes.
- Trámites: secretaría, matrículas, becas, plazos de admisión, listas de admitidos.
- Servicios: comedor, transporte, biblioteca, horarios generales.

CASOS ESPECIALES - SIEMPRE SON 'publica':
- Cualquier pregunta sobre ciclos formativos (FP, CFGS, CFGM) → 'publica'
- "Dame información sobre..." + nombre de ciclo/curso → 'publica'
- "Qué asignaturas tiene..." → 'publica'
- "Requisitos para acceder a..." → 'publica'

REGLAS DE ORO:
1. Responde ÚNICAMENTE con la palabra 'profesorado' o 'publica'.
2. NO des explicaciones. NO pidas disculpas. NO digas que no tienes acceso.
3. Si pregunta por el NOMBRE de la directora/jefe estudios/secretario → 'profesorado'.
4. Si pregunta por INFORMACIÓN ACADÉMICA (ciclos, FP, asignaturas, cursos) → 'publica'.
5. En caso de duda, elige 'publica'.
6. TU RESPUESTA DEBE SER SOLO UNA PALABRA.""")

        respuesta = await _llm_invoke_con_retry(llm_clasif, [sys_clasificador, HumanMessage(content=texto)])
        raw = _extract_text(respuesta.content).strip().lower()

        # Detectar "publica" primero (incluye variantes con/sin tilde)
        # porque la palabra "profesorado" contiene "profesor" como substring
        if any(x in raw for x in ["publica", "pública"]):
            tipo: Literal["publica", "profesorado"] = "publica"
        elif any(x in raw for x in ["profesorado", "docente", "interna"]):
            tipo = "profesorado"
        else:
            tipo = "publica"  # default seguro

        print(f"🔀 Clasificador → {tipo}  (raw: '{raw}')")
        return {"tipo_consulta": tipo}

    # ── Chatbot público ───────────────────────────────────────────────────────
    async def chatbot_publico(estado: Estado) -> dict:
        # Poda de historial: mantenemos los últimos 10 mensajes para no saturar al modelo
        mensajes = estado["messages"]
        if len(mensajes) > 10:
            mensajes = mensajes[-10:]

        tool_context = _build_tool_context(estado)
        system = SystemMessage(content=PROMPT_PUB + tool_context)
        respuesta = await _llm_invoke_con_retry(llm_pub, [system] + mensajes)

        # ── GUARDRAIL: forzar búsqueda si el LLM no llamó herramientas y no hay contexto ──
        has_context = any(isinstance(m, ToolMessage) for m in mensajes[-3:])
        if not getattr(respuesta, "tool_calls", None) and not has_context:
            query_usuario = _ultimo_mensaje_usuario(estado)
            if query_usuario and not _es_saludo(query_usuario):
                print(f"⚠️ [GUARDRAIL] LLM no llamó herramientas. Forzando búsqueda web: '{query_usuario}'")
                respuesta = AIMessage(
                    content="",
                    tool_calls=[{
                        "id": f"forced_{uuid.uuid4().hex[:8]}",
                        "name": "busqueda_web_ies_jandula",
                        "args": {"query": query_usuario + " IES Jándula 2025"},
                    }],
                )

        return {"messages": [respuesta]}

    # ── Chatbot profesorado ───────────────────────────────────────────────────
    async def chatbot_profesorado(estado: Estado) -> dict:
        # Poda de historial
        mensajes = estado["messages"]
        if len(mensajes) > 10:
            mensajes = mensajes[-10:]

        tool_context = _build_tool_context(estado)
        system = SystemMessage(content=PROMPT_PROF + tool_context)
        respuesta = await _llm_invoke_con_retry(llm_prof, [system] + mensajes)

        # ── GUARDRAIL: forzar búsqueda si el LLM no llamó herramientas y no hay contexto ──
        has_context = any(isinstance(m, ToolMessage) for m in mensajes[-3:])
        if not getattr(respuesta, "tool_calls", None) and not has_context:
            query_usuario = _ultimo_mensaje_usuario(estado)
            if query_usuario and not _es_saludo(query_usuario):
                print(f"⚠️ [GUARDRAIL] LLM no llamó herramientas. Forzando búsqueda RAG: '{query_usuario}'")
                respuesta = AIMessage(
                    content="",
                    tool_calls=[{
                        "id": f"forced_{uuid.uuid4().hex[:8]}",
                        "name": "guia_profesorado",
                        "args": {"search": query_usuario},
                    }],
                )

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
                    print(f"\n🛠️  [EJECUTANDO TOOL: {nombre}] con args: {call['args']}")
                    obs = await mapa[nombre].ainvoke(call["args"])
                    print(f"   ✅ [TOOL {nombre} COMPLETADA] Respuesta (truncada): {str(obs)[:300]}...")
            except Exception as e:
                print(f"   ❌ [ERROR EN TOOL {nombre}]: {e}")
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