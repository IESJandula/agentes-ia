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
from langchain_core.runnables import RunnableConfig
import os

# ─────────────────────────────────────────────────────────────────────────────
# Checkpointer persistente (SQLite) con fallback a MemorySaver
# ─────────────────────────────────────────────────────────────────────────────
_checkpointer = None

def _get_checkpointer():
    """
    Devuelve un checkpointer SQLite persistente si está disponible.
    Se guarda en data/chroma_db_v3/checkpoints.db para aprovechar el
    volumen persistente ya montado en Dokploy, sobreviviendo a redeployments.
    Fallback a MemorySaver si el paquete no está instalado.
    """
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer
    # AsyncSqliteSaver requiere gestión de ciclo de vida async (async with) que
    # no es compatible con nuestra arquitectura de grafo estático. Se usa
    # MemorySaver hasta implementar una solución correcta.
    _checkpointer = MemorySaver()
    print("ℹ️  [MEMORIA] Usando MemorySaver (memoria por sesión, sin persistencia entre reinicios).")
    return _checkpointer


# ─────────────────────────────────────────────────────────────────────────────
# Helper: retry con backoff para rate-limit 429 de Gemini (free tier: 5 rpm)
# ─────────────────────────────────────────────────────────────────────────────

async def _llm_invoke_con_retry(
    llm,
    mensajes,
    config: RunnableConfig | None = None,
    max_intentos: int = 4,
    espera_base: float = 20.0,
):
    """
    Llama a llm.ainvoke(mensajes) con reintentos automáticos ante 429 RESOURCE_EXHAUSTED.

    Distingue dos tipos de límite:
    - PerMinute → reintenta con backoff exponencial (espera_base * 2^i)
    - PerDay    → falla inmediatamente con mensaje claro (reintentar en segundos no sirve)
    """
    import re as _re
    for intento in range(1, max_intentos + 1):
        try:
            if config is not None:
                return await llm.ainvoke(mensajes, config=config)
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

from app.tools import obtener_tools_publicas, obtener_tools_profesorado, obtener_tools_legislacion
from .prompts.prompt_manager import (
    PROMPTS, BEHAVIOR_PUBLIC, BEHAVIOR_TEACHER, BEHAVIOR_LEGISLATION, REGLAS_VOZ
)


# ─────────────────────────────────────────────────────────────────────────────
# Estado
# ─────────────────────────────────────────────────────────────────────────────

class Estado(TypedDict):
    messages:      Annotated[list, add_messages]
    tipo_consulta: Literal["publica", "profesorado", "legislacion"] | None


# ─────────────────────────────────────────────────────────────────────────────
# Construcción del grafo
# ─────────────────────────────────────────────────────────────────────────────

async def configurar_grafo_ies(perfil: str, es_voz: bool = False):

    # ── 1. Tools por fuente ──────────────────────────────────────────────────
    tools_pub   = await obtener_tools_publicas()
    tools_prof  = await obtener_tools_profesorado() if perfil == "profesores" else []
    tools_legis = await obtener_tools_legislacion()

    map_pub   = {t.name: t for t in tools_pub}
    map_prof  = {t.name: t for t in tools_prof}
    map_legis = {t.name: t for t in tools_legis}
    map_todo  = {**map_pub, **map_prof, **map_legis}

    # ── 2. Prompts ───────────────────────────────────────────────────────────
    _voz_suffix  = REGLAS_VOZ if es_voz else ""
    PROMPT_PUB   = PROMPTS[perfil] + "\n\n" + BEHAVIOR_PUBLIC       + _voz_suffix
    PROMPT_PROF  = PROMPTS[perfil] + "\n\n" + BEHAVIOR_TEACHER      + _voz_suffix
    PROMPT_LEGIS = PROMPTS[perfil] + "\n\n" + BEHAVIOR_LEGISLATION  + _voz_suffix

    # ── 3. LLMs ─────────────────────────────────────────────────────────────
    # Modelo configurable por variable de entorno para facilitar el cambio.
    # Opciones recomendadas (AI Studio free tier, de menor a mayor cuota):
    #   gemini-3-flash-preview  →  20 req/día  (evitar)
    #   gemini-2.0-flash-lite   →  200 req/día
    #   gemini-1.5-flash        →  1500 req/día ← recomendado para desarrollo
    if not os.getenv("GOOGLE_API_KEY"):
        raise ValueError("⚠️ GOOGLE_API_KEY no está configurada en las variables de entorno")

    _model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    print(f"   🤖 Usando modelo LLM: {_model_name}")
    _base_llm  = ChatGoogleGenerativeAI(
        model=_model_name,
        temperature=0.4,
        max_retries=3,
        streaming=True,
    )
    # Clasificador determinista: temperatura 0 para enrutar de forma estable.
    llm_clasif = ChatGoogleGenerativeAI(
        model=_model_name,
        temperature=0.0,
        max_retries=3,
        streaming=False,
    )                                                                              # sin tools
    llm_pub    = _base_llm.bind_tools(tools_pub)   if tools_pub   else _base_llm
    llm_prof   = _base_llm.bind_tools(tools_prof)  if tools_prof  else _base_llm
    llm_legis  = _base_llm.bind_tools(tools_legis) if tools_legis else _base_llm

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

    # ── Helper: ¿ya se forzó una búsqueda en este turno? ──────────────────────
    def _guardrail_ya_usado(estado: Estado) -> bool:
        """True si en el turno actual (desde el último HumanMessage) ya forzamos
        una tool_call. Evita bucles de guardrail que agotan recursion_limit/cuota."""
        for m in reversed(estado["messages"]):
            if isinstance(m, HumanMessage):
                return False
            if isinstance(m, AIMessage) and m.additional_kwargs.get("forced_guardrail"):
                return True
        return False

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
    async def clasificar(estado: Estado, config: RunnableConfig) -> dict:
        """Decide si la consulta es pública o interna de profesorado."""
        if perfil != "profesores" or not tools_prof:
            return {"tipo_consulta": "publica"}

        ultimo = estado["messages"][-1]
        texto  = ultimo.content if hasattr(ultimo, "content") else str(ultimo)

        sys_clasificador = SystemMessage(content="""Eres un sistema de enrutamiento estricto para el IES Jándula.
Tu ÚNICA función es clasificar la consulta del usuario en una de estas TRES categorías.

CATEGORÍA 'legislacion' (normativa y leyes educativas):
- Leyes educativas nacionales: LOMLOE, LOE, LOGSE, Estatuto Docente, Ley FP 3/2022.
- Decretos u órdenes de la Junta de Andalucía sobre educación, evaluación o currículo.
- Instrucciones de inicio de curso de la Consejería de Educación.
- Normativa sobre evaluación, titulación, acceso a ciclos formativos o universidad.
- Derechos y deberes legales del profesorado o del alumnado (marco legislativo).
- Convocatorias de oposiciones o concursos docentes (BOE/BOJA).
- Cualquier pregunta que empiece con "¿Qué dice la ley...", "¿Está regulado...", "¿Cuál es la normativa...".

CATEGORÍA 'profesorado' (información INTERNA del centro):
- Nombres ESPECÍFICOS de profesores, tutores o jefes de departamento.
- Cargos del EQUIPO DIRECTIVO: directora, jefe de estudios, secretario/a.
- Documentación interna: planes (acogida, igualdad), protocolos (incendio, accidentes), NOF, PEC, ROF, actas.
- Gestión docente: guardias, Séneca, partes de incidencias, sustituciones, reuniones de departamento.

CATEGORÍA 'publica' (información accesible en la web del centro):
- Todo sobre ciclos formativos, FP, ESO, Bachillerato (descripción, asignaturas, requisitos, salidas).
- Noticias, eventos, calendario escolar, actividades extraescolares, clubes.
- Trámites: secretaría, matrículas, becas, plazos de admisión, listas de admitidos.
- Servicios: comedor, transporte, biblioteca, horarios generales.

REGLAS DE ORO:
1. Responde ÚNICAMENTE con una de estas palabras: 'legislacion', 'profesorado' o 'publica'.
2. NO des explicaciones ni pidas disculpas.
3. Si pregunta por una ley, decreto, orden, LOMLOE, BOE, BOJA → 'legislacion'.
4. Si pregunta por el NOMBRE de un cargo directivo o normativa INTERNA del centro → 'profesorado'.
5. Si pregunta por INFORMACIÓN ACADÉMICA PÚBLICA (ciclos, FP, matrículas) → 'publica'.
6. En caso de duda entre 'legislacion' y 'profesorado' → 'legislacion'.
7. En caso de duda general → 'publica'.
8. TU RESPUESTA DEBE SER SOLO UNA PALABRA.""")

        respuesta = await _llm_invoke_con_retry(llm_clasif, [sys_clasificador, HumanMessage(content=texto)], config=config)
        raw = _extract_text(respuesta.content).strip().lower()

        # Detectar categoría — orden importante: legislacion > profesorado > publica
        if any(x in raw for x in ["legislacion", "legislación", "legal", "normativa"]):
            tipo: Literal["publica", "profesorado", "legislacion"] = "legislacion"
        elif any(x in raw for x in ["publica", "pública"]):
            tipo = "publica"
        elif any(x in raw for x in ["profesorado", "docente", "interna"]):
            tipo = "profesorado"
        else:
            tipo = "publica"  # default seguro

        print(f"🔀 Clasificador → {tipo}  (raw: '{raw}')")
        return {"tipo_consulta": tipo}

    # ── Chatbot público ───────────────────────────────────────────────────────
    async def chatbot_publico(estado: Estado, config: RunnableConfig) -> dict:
        # Poda de historial inteligente: no cortamos en medio de una cadena Tool -> AI
        mensajes = estado["messages"]
        if len(mensajes) > 12:
            # Buscamos el HumanMessage más antiguo dentro de los últimos 12 para no romper la cadena
            for i in range(len(mensajes) - 12, len(mensajes)):
                if isinstance(mensajes[i], HumanMessage):
                    mensajes = mensajes[i:]
                    break
            else:
                mensajes = mensajes[-10:]

        tool_context = _build_tool_context(estado)
        system = SystemMessage(content=PROMPT_PUB + tool_context)
        
        # Google requiere que el primer mensaje tras el System sea un HumanMessage
        # o que la secuencia sea coherente.
        respuesta = await _llm_invoke_con_retry(llm_pub, [system] + mensajes, config=config)

        # ── GUARDRAIL: forzar búsqueda si el LLM no llamó herramientas y no hay contexto ──
        has_context = any(isinstance(m, ToolMessage) for m in mensajes[-3:])
        if not getattr(respuesta, "tool_calls", None) and not has_context and not _guardrail_ya_usado(estado):
            query_usuario = _ultimo_mensaje_usuario(estado)
            if query_usuario and not _es_saludo(query_usuario):
                print(f"⚠️ [GUARDRAIL] LLM no llamó herramientas. Forzando búsqueda web: '{query_usuario}'")
                respuesta = AIMessage(
                    content="",
                    additional_kwargs={"forced_guardrail": True},
                    tool_calls=[{
                        "id": f"forced_{uuid.uuid4().hex[:8]}",
                        "name": "busqueda_web_ies_jandula",
                        "args": {"query": query_usuario + " IES Jándula 2025"},
                    }],
                )

        return {"messages": [respuesta]}

    # ── Chatbot legislación ───────────────────────────────────────────────────
    async def chatbot_legislacion(estado: Estado, config: RunnableConfig) -> dict:
        mensajes = estado["messages"]
        if len(mensajes) > 12:
            for i in range(len(mensajes) - 12, len(mensajes)):
                if isinstance(mensajes[i], HumanMessage):
                    mensajes = mensajes[i:]
                    break
            else:
                mensajes = mensajes[-10:]

        tool_context = _build_tool_context(estado)
        system = SystemMessage(content=PROMPT_LEGIS + tool_context)
        respuesta = await _llm_invoke_con_retry(llm_legis, [system] + mensajes, config=config)

        # Guardrail: si no llamó herramientas y no hay contexto, forzar búsqueda legislativa
        has_context = any(isinstance(m, ToolMessage) for m in mensajes[-3:])
        if not getattr(respuesta, "tool_calls", None) and not has_context and not _guardrail_ya_usado(estado):
            query_usuario = _ultimo_mensaje_usuario(estado)
            if query_usuario and not _es_saludo(query_usuario):
                print(f"⚠️ [GUARDRAIL] Forzando búsqueda legislativa: '{query_usuario}'")
                respuesta = AIMessage(
                    content="",
                    additional_kwargs={"forced_guardrail": True},
                    tool_calls=[{
                        "id": f"forced_{uuid.uuid4().hex[:8]}",
                        "name": "busqueda_legislacion_educativa",
                        "args": {"query": query_usuario + " normativa educativa España 2025"},
                    }],
                )

        return {"messages": [respuesta]}

    # ── Chatbot profesorado ───────────────────────────────────────────────────
    async def chatbot_profesorado(estado: Estado, config: RunnableConfig) -> dict:
        # Poda de historial inteligente
        mensajes = estado["messages"]
        if len(mensajes) > 12:
            for i in range(len(mensajes) - 12, len(mensajes)):
                if isinstance(mensajes[i], HumanMessage):
                    mensajes = mensajes[i:]
                    break
            else:
                mensajes = mensajes[-10:]

        tool_context = _build_tool_context(estado)
        system = SystemMessage(content=PROMPT_PROF + tool_context)
        respuesta = await _llm_invoke_con_retry(llm_prof, [system] + mensajes, config=config)

        # ── GUARDRAIL: forzar búsqueda si el LLM no llamó herramientas y no hay contexto ──
        has_context = any(isinstance(m, ToolMessage) for m in mensajes[-3:])
        if not getattr(respuesta, "tool_calls", None) and not has_context and not _guardrail_ya_usado(estado):
            query_usuario = _ultimo_mensaje_usuario(estado)
            if query_usuario and not _es_saludo(query_usuario):
                print(f"⚠️ [GUARDRAIL] LLM no llamó herramientas. Forzando búsqueda RAG: '{query_usuario}'")
                respuesta = AIMessage(
                    content="",
                    additional_kwargs={"forced_guardrail": True},
                    tool_calls=[{
                        "id": f"forced_{uuid.uuid4().hex[:8]}",
                        "name": "guia_profesorado",
                        "args": {"search": query_usuario},
                    }],
                )

        return {"messages": [respuesta]}

    # ── Ejecutor de tools (paralelo + timeout + auto-aprendizaje) ────────────
    _TOOL_TIMEOUT = float(os.getenv("TOOL_TIMEOUT_SECONDS", "15"))
    # Auto-indexado de búsquedas web en ChromaDB. Desactivable por env para evitar
    # contaminar el RAG y reducir escrituras concurrentes a HNSW/SQLite.
    _AUTOLEARN_ACTIVO = os.getenv("AUTOLEARN_ACTIVO", "false").lower() in ("1", "true", "yes")
    # Tools cuyo output se auto-indexa en ChromaDB para aprendizaje continuo
    _TOOLS_AUTOLEARN = {"busqueda_legislacion_educativa", "busqueda_web_general"}

    async def ejecutar_tools(estado: Estado) -> dict:
        ultimo  = estado["messages"][-1]
        tipo    = estado.get("tipo_consulta", "publica")
        if tipo == "profesorado":
            mapa = map_prof
        elif tipo == "legislacion":
            mapa = map_legis
        else:
            mapa = map_pub

        async def _run_single(call: dict) -> ToolMessage:
            nombre = call["name"]
            if nombre not in mapa:
                obs = (
                    f"⚠️ La herramienta '{nombre}' no está disponible "
                    f"en la rama '{tipo}'. Usa solo las herramientas permitidas."
                )
                return ToolMessage(content=obs, tool_call_id=call["id"], name=nombre)
            try:
                print(f"\n🛠️  [TOOL: {nombre}] args={call['args']}")
                obs = await asyncio.wait_for(
                    mapa[nombre].ainvoke(call["args"]),
                    timeout=_TOOL_TIMEOUT,
                )
                print(f"   ✅ [TOOL {nombre}] OK — {len(str(obs))} chars")

                # Auto-aprendizaje: indexar resultados de búsquedas web en background
                obs_str = str(obs)
                if _AUTOLEARN_ACTIVO and nombre in _TOOLS_AUTOLEARN and len(obs_str) > 500:
                    query = call["args"].get("query", call["args"].get("search", ""))
                    async def _autolearn(content=obs_str, q=query, n=nombre):
                        try:
                            from data.data import auto_indexar_resultado_web
                            n_chunks = auto_indexar_resultado_web(content, q, n)
                            if n_chunks:
                                print(f"   🧠 [AUTO-LEARN] {n_chunks} nuevos fragmentos indexados.")
                        except Exception as ae:
                            print(f"   ⚠️ [AUTO-LEARN] {ae}")
                    asyncio.create_task(_autolearn())

            except asyncio.TimeoutError:
                print(f"   ⏱️  [TOOL {nombre}] Timeout tras {_TOOL_TIMEOUT}s")
                obs = f"⚠️ La herramienta '{nombre}' tardó demasiado (>{_TOOL_TIMEOUT}s). Intenta reformular la pregunta."
            except Exception as e:
                print(f"   ❌ [TOOL {nombre}] Error: {e}")
                obs = f"Error en herramienta '{nombre}': {e}"
            return ToolMessage(content=str(obs), tool_call_id=call["id"], name=nombre)

        # Ejecutar todas las tool_calls en paralelo
        results = await asyncio.gather(*[_run_single(c) for c in ultimo.tool_calls])
        return {"messages": list(results)}

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

    def route_chatbot_legislacion(estado: Estado) -> str:
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
    builder.add_node("chatbot_legislacion",  chatbot_legislacion)
    builder.add_node("tools",                ejecutar_tools)

    builder.add_edge(START, "clasificar")

    builder.add_conditional_edges(
        "clasificar",
        route_tras_clasificar,
        {
            "publica":      "chatbot_publico",
            "profesorado":  "chatbot_profesorado",
            "legislacion":  "chatbot_legislacion",
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
        "chatbot_legislacion",
        route_chatbot_legislacion,
        {"tools": "tools", END: END},
    )

    builder.add_conditional_edges(
        "tools",
        route_tras_tools,
        {
            "publica":      "chatbot_publico",
            "profesorado":  "chatbot_profesorado",
            "legislacion":  "chatbot_legislacion",
        },
    )

    grafo = builder.compile(checkpointer=_get_checkpointer())
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