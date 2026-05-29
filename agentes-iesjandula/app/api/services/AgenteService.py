import asyncio
import os
import shutil
import tempfile
import time
from typing import AsyncGenerator

from fastapi import UploadFile
from app.agents import AgenteJandula
from app.api.services.CacheService import cache_service
from app.api.services.AdminService import admin_service


class AgentsService:
    def __init__(self):
        self._agentes = {}

    async def _get_or_create_agente(self, perfil: str, modo: str) -> AgenteJandula:
        clave = f"{perfil}_{modo}"
        if clave not in self._agentes:
            print(f"🚀 Inicializando agente: {perfil} en modo {modo}...")
            agente = AgenteJandula(perfil=perfil, modo=modo)
            await agente.encender()
            self._agentes[clave] = agente
            print(f"✅ Agente {clave} listo.")
        return self._agentes[clave]

    async def procesar_chat(
        self,
        pregunta: str,
        perfil: str = "profesores",
        thread_id: str | None = None,
    ) -> dict:
        """
        Maneja consultas de texto. Devuelve dict con 'respuesta' y 'fuentes'.
        Consulta la caché antes de invocar el LLM.
        """
        tid = thread_id or "default"

        # --- Caché (solo para threads genéricos, no sesiones personales) ---
        usar_cache = tid == "default"
        if usar_cache:
            cached = cache_service.get(pregunta, perfil)
            if cached:
                admin_service.registrar_consulta(
                    pregunta, perfil, cached.get("fuentes", []), desde_cache=True
                )
                return cached

        # --- Invocar agente ---
        t0 = time.time()
        agente = await self._get_or_create_agente(perfil, "texto")
        resultado = await agente.responder(pregunta, thread_id=tid)
        tiempo_ms = int((time.time() - t0) * 1000)

        # resultado puede ser dict (modo texto) o str (warmup legacy)
        if isinstance(resultado, str):
            resultado = {"respuesta": resultado, "fuentes": []}

        # --- Guardar en caché y registrar uso ---
        if usar_cache:
            cache_service.set(pregunta, perfil, resultado)

        admin_service.registrar_consulta(
            pregunta, perfil, resultado.get("fuentes", []),
            desde_cache=False, tiempo_ms=tiempo_ms,
        )

        return resultado

    async def stream_chat(
        self,
        pregunta: str,
        perfil: str = "profesores",
        thread_id: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Generador async de eventos SSE para streaming de respuesta."""
        tid = thread_id or "default"
        agente = await self._get_or_create_agente(perfil, "texto")
        async for evento in agente.responder_stream(pregunta, thread_id=tid):
            yield evento
            if evento.get("tipo") == "fin":
                admin_service.registrar_consulta(
                    pregunta, perfil, evento.get("fuentes", []), desde_cache=False
                )

    async def procesar_voz(self, audio_file: UploadFile, perfil: str = "profesores"):
        agente = await self._get_or_create_agente(perfil, "voz")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            shutil.copyfileobj(audio_file.file, tmp)
            ruta_entrada = tmp.name
        try:
            ruta_salida = await agente.responder(ruta_entrada)
            if not os.path.exists(ruta_salida):
                raise FileNotFoundError("No se generó el audio de salida.")
            return ruta_salida, ruta_entrada
        except Exception as e:
            if os.path.exists(ruta_entrada):
                os.remove(ruta_entrada)
            raise e

    async def procesar_hibrido(self, audio_file: UploadFile, perfil: str = "profesores"):
        agente = await self._get_or_create_agente(perfil, "hibrido")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            shutil.copyfileobj(audio_file.file, tmp)
            ruta_entrada = tmp.name
        try:
            return await agente.responder(ruta_entrada)
        finally:
            if os.path.exists(ruta_entrada):
                os.remove(ruta_entrada)


agents_service = AgentsService()
