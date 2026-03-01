import asyncio
import os
import shutil
import tempfile
from fastapi import UploadFile

from app.agents.agente_profesores import inicializar_agente_profesores
from app.agents import AgenteVozJandula, AgenteHibridoJandula

class AgentsService:
    def __init__(self):
        self._agente_grafo = None
        self._agente_voz = None
        self._agente_hibrido = None

    async def get_agente_texto(self):
        if self._agente_grafo is None:
            print("🚀 Inicializando agente texto...")
            self._agente_grafo = await inicializar_agente_profesores()
            print("✅ Agente texto inicializado.")
        return self._agente_grafo

    async def get_agente_voz(self):
        if self._agente_voz is None:
            print("🚀 Inicializando agente VOZ...")
            self._agente_voz = AgenteVozJandula()
            await self._agente_voz.inicializar()
            print("✅ Agente VOZ inicializado.")
        return self._agente_voz

    async def get_agente_hibrido(self):
        if self._agente_hibrido is None:
            print("🚀 Inicializando agente HÍBRIDO...")
            self._agente_hibrido = AgenteHibridoJandula()
            await self._agente_hibrido.inicializar()
            print("✅ Agente HÍBRIDO inicializado.")
        return self._agente_hibrido

    async def procesar_chat(self, pregunta: str) -> str:
        """
        Retorna solo el string de respuesta. 
        El Controller se encargará de envolverlo en el modelo ConsultaResponse.
        """
        agente = await self.get_agente_texto()
        
        respuesta = await asyncio.wait_for(
            agente.ainvoke(
                {"messages": [("user", pregunta)]},
                {"configurable": {"thread_id": "default"}, "recursion_limit": 25}
            ),
            timeout=300
        )
        
        mensajes = respuesta.get("messages", [])
        if not mensajes:
            return "No se obtuvo respuesta del agente"
        
        ultimo = mensajes[-1]
        if isinstance(ultimo, tuple): return ultimo[1]
        if hasattr(ultimo, "content"): return str(ultimo.content)
        return str(ultimo)

    async def procesar_voz(self, audio_file: UploadFile) -> tuple[str, str]:
        """Retorna una tupla (ruta_salida, ruta_entrada)"""
        agente = await self.get_agente_voz()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            shutil.copyfileobj(audio_file.file, tmp)
            ruta_entrada = tmp.name

        try:
            ruta_salida = await asyncio.wait_for(
                agente.interactuar(ruta_entrada),
                timeout=300
            )
            if not os.path.exists(ruta_salida):
                raise FileNotFoundError("El agente no generó el archivo de audio de salida.")
            return ruta_salida, ruta_entrada
        except Exception as e:
            if os.path.exists(ruta_entrada): 
                os.remove(ruta_entrada)
            raise e

    async def procesar_hibrido(self, audio_file: UploadFile) -> dict:
        """Retorna el diccionario con la transcripción y la respuesta"""
        agente = await self.get_agente_hibrido()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            shutil.copyfileobj(audio_file.file, tmp)
            ruta_entrada = tmp.name

        try:
            resultado = await asyncio.wait_for(
                agente.consultar(ruta_entrada),
                timeout=300
            )
            return resultado
        finally:
            if os.path.exists(ruta_entrada):
                os.remove(ruta_entrada)

agents_service = AgentsService()