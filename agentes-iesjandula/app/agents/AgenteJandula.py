import re
from langchain_core.messages import ToolMessage
from .AgentConfig import configurar_grafo_ies
from .abilities.Audio import MotorVoz

# Nodos que generan la respuesta final (no el clasificador ni las tools)
_NODOS_RESPUESTA = {"chatbot_publico", "chatbot_profesorado"}


def _extraer_fuentes(mensajes: list) -> list[str]:
    """Extrae nombres de documentos fuente de los ToolMessages del último turno."""
    fuentes = set()
    for msg in mensajes:
        if isinstance(msg, ToolMessage) and msg.name in ("guia_profesorado", "guia_alumnado"):
            for match in re.findall(r'\[Fuente:\s*([^\]]+)\]', msg.content):
                fuentes.add(match.strip())
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

        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 15}
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
          {"tipo": "fin",         "fuentes": [...]}              → respuesta completada
        """
        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 15}
        fuentes: set[str] = set()
        # Buffer para descartar tokens previos si una tool se activa después
        buffer_tokens: list[str] = []
        tool_fired = False

        async for event in self.grafo.astream_events(
            {"messages": [("user", entrada)]},
            config=config,
            version="v2",
        ):
            etype = event["event"]
            nodo  = event.get("metadata", {}).get("langgraph_node", "")

            if etype == "on_tool_start":
                # Si había tokens en buffer previos a la tool, descartarlos
                buffer_tokens.clear()
                tool_fired = True
                yield {"tipo": "herramienta", "nombre": event.get("name", "herramienta")}

            elif etype == "on_tool_end":
                # Extraer fuentes del output de la tool
                output = str(event["data"].get("output", ""))
                for match in re.findall(r'\[Fuente:\s*([^\]]+)\]', output):
                    fuentes.add(match.strip())

            elif etype == "on_chat_model_stream" and nodo in _NODOS_RESPUESTA:
                chunk = event["data"]["chunk"]
                content = chunk.content
                # Solo emitir si es texto real (no tool_call_chunks vacíos)
                if content and isinstance(content, str) and content.strip():
                    buffer_tokens.append(content)
                    yield {"tipo": "token", "texto": content}

        yield {"tipo": "fin", "fuentes": sorted(fuentes)}
