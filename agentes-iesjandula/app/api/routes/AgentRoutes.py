import json
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import StreamingResponse
from app.api.controllers import AgenteController
from app.api.models import ConsultaRequest, ConsultaResponse

router = APIRouter(tags=["Agente"])


@router.post("/chat", response_model=ConsultaResponse)
async def consultar_agente(consulta: ConsultaRequest):
    return await AgenteController.handle_chat(
        consulta.pregunta,
        perfil=consulta.perfil,
        thread_id=consulta.thread_id,
    )


@router.post("/chat/stream")
async def stream_agente(consulta: ConsultaRequest):
    """Endpoint SSE: devuelve la respuesta token a token."""
    async def generator():
        async for evento in AgenteController.handle_chat_stream(
            consulta.pregunta,
            perfil=consulta.perfil,
            thread_id=consulta.thread_id,
        ):
            yield f"data: {json.dumps(evento, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Evita buffering en Nginx/Traefik
        },
    )


@router.post("/speak")
async def consultar_agente_voz(audio_file: UploadFile = File(...), perfil: str = "profesores"):
    return await AgenteController.handle_speak(audio_file, perfil=perfil)


@router.post("/transcribe")
async def consultar_agente_hibrido(audio_file: UploadFile = File(...), perfil: str = "profesores"):
    return await AgenteController.handle_transcribe(audio_file, perfil=perfil)


@router.get("/health")
async def health_check():
    return {"status": "ok", "servicio": "Agente IES Jándula"}
