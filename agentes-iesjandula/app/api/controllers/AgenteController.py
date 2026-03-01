from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse
import traceback
import os
from app.api.services import agents_service
from app.api.models import ConsultaResponse 

class AgenteController:
    @staticmethod
    async def handle_chat(pregunta: str, perfil: str = "profesores") -> ConsultaResponse:
        try:
            texto = await agents_service.procesar_chat(pregunta, perfil=perfil)
            return ConsultaResponse(respuesta=texto)
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def handle_speak(audio_file: UploadFile, perfil: str = "profesores"):
        try:
            ruta_salida, ruta_entrada = await agents_service.procesar_voz(audio_file, perfil=perfil)
            
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
    async def handle_transcribe(audio_file: UploadFile, perfil: str = "profesores"):
        try:
            return await agents_service.procesar_hibrido(audio_file, perfil=perfil)
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Error híbrido: {str(e)}")