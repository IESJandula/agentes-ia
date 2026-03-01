from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse
import traceback
import os
from app.api.services import agents_service
from app.api.models import ConsultaResponse 

class AgenteController:
    @staticmethod
    async def handle_chat(pregunta: str) -> ConsultaResponse:
        try:
            texto = await agents_service.procesar_chat(pregunta)
            return ConsultaResponse(respuesta=texto)
            
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def handle_speak(audio_file: UploadFile):
        try:
            ruta_salida, ruta_entrada = await agents_service.procesar_voz(audio_file)
            
            response = FileResponse(
                path=ruta_salida,
                media_type="audio/wav",
                filename="respuesta_jandula.wav"
            )
            
            if os.path.exists(ruta_entrada): 
                os.remove(ruta_entrada)
            return response
            
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Error en voz: {str(e)}")

    @staticmethod
    async def handle_transcribe(audio_file: UploadFile):
        try:
            return await agents_service.procesar_hibrido(audio_file)
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Error híbrido: {str(e)}")