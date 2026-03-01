import asyncio
import os
import shutil
import tempfile
from fastapi import UploadFile

from app.agents import AgenteJandula

class AgentsService:
    def __init__(self):
        self._agentes = {}

    async def _get_or_create_agente(self, perfil: str, modo: str) -> AgenteJandula:
        """Obtiene o inicializa el agente específico según perfil y modo."""
        clave = f"{perfil}_{modo}"
        if clave not in self._agentes:
            print(f"🚀 Inicializando agente: {perfil} en modo {modo}...")
            agente = AgenteJandula(perfil=perfil, modo=modo)
            await agente.encender()
            self._agentes[clave] = agente
            print(f"✅ Agente {clave} listo.")
        return self._agentes[clave]

    async def procesar_chat(self, pregunta: str, perfil: str = "profesores") -> str:
        """Maneja consultas de texto puro."""
        agente = await self._get_or_create_agente(perfil, "texto")
        return await agente.responder(pregunta)

    async def procesar_voz(self, audio_file: UploadFile, perfil: str = "profesores") -> tuple[str, str]:
        """Maneja entrada de voz y salida de voz."""
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

    async def procesar_hibrido(self, audio_file: UploadFile, perfil: str = "profesores") -> dict:
        """Maneja entrada de voz y salida de texto (transcripción + respuesta)."""
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