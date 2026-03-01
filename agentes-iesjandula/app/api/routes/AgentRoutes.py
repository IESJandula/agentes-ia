from fastapi import APIRouter, UploadFile, File
from app.api.controllers import AgenteController
from app.api.models import ConsultaRequest, ConsultaResponse

router = APIRouter(tags=["Agente"])

@router.post("/chat", response_model=ConsultaResponse)
async def consultar_agente(consulta: ConsultaRequest):
    return await AgenteController.handle_chat(consulta.pregunta)

@router.post("/speak")
async def consultar_agente_voz(audio_file: UploadFile = File(...)):
    return await AgenteController.handle_speak(audio_file)

@router.post("/transcribe")
async def consultar_agente_hibrido(audio_file: UploadFile = File(...)):
    return await AgenteController.handle_transcribe(audio_file)

@router.get("/health")
async def health_check():
    return {"status": "ok", "servicio": "Agente IES Jándula"}