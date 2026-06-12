import asyncio
import re
from langchain_core.messages import ToolMessage
from .AgentConfig import configurar_grafo_ies
from .abilities.Audio import MotorVoz

# Nodos que generan la respuesta final (no el clasificador ni las tools)
_NODOS_RESPUESTA = {"chatbot_publico", "chatbot_profesorado", "chatbot_legislacion"}

# Tools RAG que emiten [Fuente: filename]
_TOOLS_RAG = {"guia_profesorado", "guia_alumnado", "consultar_conocimiento_aprendido"}
# Tools web que emiten FUENTE: https://...
_TOOLS_WEB = {
    "busqueda_web_ies_jandula", "busqueda_web_general",
    "busqueda_legislacion_educativa",
}


def _extraer_fuentes(mensajes: list) -> list[str]:
    """
    Extrae fuentes de los ToolMessages:
    - RAG: [Fuente: nombre_archivo]
    - Web: FUENTE: https://...  (devueltas como URLs para mostrar como chips clicables)
    """
    fuentes = set()
    for msg in mensajes:
        if not isinstance(msg, ToolMessage):
            continue
        if msg.name in _TOOLS_RAG:
            for match in re.findall(r'\[Fuente:\s*([^\]]+)\]', msg.content):
                fuentes.add(match.strip())
        elif msg.name in _TOOLS_WEB:
            for match in re.findall(r'FUENTE:\s*(https?://\S+)', msg.content):
                fuentes.add(match.strip().rstrip('.,)'))
    return sorted(fuentes)


class AgenteJandula:
    def __init__(self, perfil: str, modo: str):
        self.perfil = perfil
        self.modo = modo
        self.grafo = None
        self.motor_voz = None

    async def encender(self):
        self.grafo = await configurar_grafo_ies(self.perfil, es_voz=(self.modo == "voz"))
        if self.modo in ["voz", "hibrido"]:
            self.motor_voz = MotorVoz()

    async def responder(self, entrada, thread_id="default") -> dict:
        """Devuelve dict con 'respuesta' (str) y 'fuentes' (list[str])."""
        texto_usuario = entrada
        if self.modo in ["voz", "hibrido"]:
            texto_usuario = self.motor_voz.escuchar(entrada)

        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 8}
        resultado = await self.grafo.ainvoke({"messages": [("user", texto_usuario)]}, config)

        # Extraer texto de forma segura (soporta str y list/multimodal)
        raw_content = resultado["messages"][-1].content
        if isinstance(raw_content, list):
            respuesta_texto = " ".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in raw_content
            )
        else:
            respuesta_texto = str(raw_content)

        fuentes = _extraer_fuentes(resultado["messages"])

        if self.modo == "voz":
            return self.motor_voz.hablar(respuesta_texto)

        if self.modo == "hibrido":
            return {"transcripcion": texto_usuario, "respuesta": respuesta_texto}

        print(f"🤖 Respuesta enviada ({len(respuesta_texto)} caracteres) | Fuentes: {fuentes}")
        return {"respuesta": respuesta_texto, "fuentes": fuentes}

    async def responder_stream(self, entrada: str, thread_id: str = "default"):
        """
        Generador async que emite eventos SSE:
          {"tipo": "herramienta", "nombre": "guia_profesorado"}  → tool en ejecución
          {"tipo": "token",       "texto": "..."}                → fragmento de texto
          {"tipo": "error",       "mensaje": "..."}              → error recuperable
          {"tipo": "fin",         "fuentes": [...]}              → respuesta completada
        """
        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 8}
        fuentes: set[str] = set()
        tokens_emitidos: int = 0
        post_tool_phase: bool = False
        nodos_clasificador = {"clasificar", "clasificador", "classify"}
        _debug_eventos: dict[str, int] = {}

        try:
            async for event in self.grafo.astream_events(
                {"messages": [("user", entrada)]},
                config=config,
                version="v2",
            ):
                etype = event["event"]
                _debug_eventos[etype] = _debug_eventos.get(etype, 0) + 1
                metadata = event.get("metadata", {})
                nodo = (metadata.get("langgraph_node") or metadata.get("node") or "")

                if etype == "on_tool_start":
                    # Marcar que ya pasamos por una tool; a partir de aquí los tokens son reales
                    post_tool_phase = True
                    yield {"tipo": "herramienta", "nombre": event.get("name", "herramienta")}

                elif etype == "on_tool_end":
                    # Extraer fuentes del output de la tool
                    output = str(event["data"].get("output", ""))
                    for match in re.findall(r'\[Fuente:\s*([^\]]+)\]', output):
                        fuentes.add(match.strip())

                elif etype == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    content = chunk.content

                    # Normalizar content multimodal (list de dicts con "text")
                    if isinstance(content, list):
                        content = "".join(
                            p.get("text", "") if isinstance(p, dict) else str(p)
                            for p in content
                        )

                    # Descartar vacíos o no-str
                    if not content or not isinstance(content, str):
                        continue

                    # Descartar tool_call_chunks (el LLM está construyendo una llamada, no respondiendo)
                    if getattr(chunk, "tool_call_chunks", None):
                        continue

                    # Descartar tokens del clasificador
                    if nodo in nodos_clasificador:
                        continue

                    # Emitir si es un nodo de respuesta, o si ya pasamos por una tool, o si el nodo es desconocido
                    if nodo in _NODOS_RESPUESTA or post_tool_phase or not nodo:
                        tokens_emitidos += 1
                        yield {"tipo": "token", "texto": content}

        except Exception as e:
            print(f"❌ [STREAM ERROR] {e}")
            yield {"tipo": "error", "mensaje": str(e)}
            yield {"tipo": "fin", "fuentes": []}
            return

        print(f"📊 [STREAM DEBUG] eventos recibidos: {_debug_eventos}")
        print(f"   tokens_emitidos={tokens_emitidos}  post_tool={post_tool_phase}")

        # ── Fallback: si no llegó ningún token, recuperar respuesta del estado ──
        if tokens_emitidos == 0:
            print("⚠️  [STREAM] Fallback → recuperando respuesta del estado del grafo...")
            try:
                estado = await self.grafo.aget_state(config)
                mensajes = estado.values.get("messages", []) if estado else []
                ultimo = mensajes[-1] if mensajes else None

                if ultimo is not None and not getattr(ultimo, "tool_calls", None):
                    raw = ultimo.content
                    if isinstance(raw, list):
                        texto = "".join(
                            p.get("text", "") if isinstance(p, dict) else str(p) for p in raw
                        )
                    else:
                        texto = str(raw)

                    # Reutilizar fuentes del estado si las hay
                    fuentes = set(_extraer_fuentes(mensajes))

                    # Emitir palabra a palabra para simular streaming y forzar flush SSE
                    palabras = texto.split(" ")
                    for i, palabra in enumerate(palabras):
                        fragmento = palabra if i == len(palabras) - 1 else palabra + " "
                        yield {"tipo": "token", "texto": fragmento}
                        await asyncio.sleep(0)  # cede el event loop → flush SSE chunk
                else:
                    yield {"tipo": "error", "mensaje": "No se pudo generar una respuesta."}

            except Exception as e2:
                print(f"❌ [FALLBACK ERROR] {e2}")
                yield {"tipo": "error", "mensaje": str(e2)}

        yield {"tipo": "fin", "fuentes": sorted(fuentes)}
