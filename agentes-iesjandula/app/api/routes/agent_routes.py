"""
Rutas para consultar al agente de IES Jándula.
Versión completamente ASYNC (sin run_in_executor).
"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from fastapi.responses import FileResponse
import asyncio
import shutil
import os
import tempfile
import traceback

from app.agents.agente_profesores import inicializar_agente_profesores
from app.agents import AgenteVozJandula
from app.agents import AgenteHibridoJandula


router = APIRouter(tags=["Agente"])


# ==============================
# MODELOS
# ==============================

class ConsultaRequest(BaseModel):
    pregunta: str


class ConsultaResponse(BaseModel):
    respuesta: str


# ==============================
# VARIABLES GLOBALES
# ==============================

_agente_grafo = None
_agente_voz = None
_agente_hibrido = None


# ==============================
# INICIALIZACIÓN
# ==============================

async def inicializar_agente_app():
    global _agente_grafo

    if _agente_grafo is None:
        print("🚀 Inicializando agente texto...")
        _agente_grafo = await inicializar_agente_profesores()
        print("✅ Agente texto inicializado.")


async def inicializar_agente_voz_app():
    global _agente_voz

    if _agente_voz is None:
        print("🚀 Inicializando agente VOZ...")
        _agente_voz = AgenteVozJandula()
        await _agente_voz.inicializar()
        print("✅ Agente VOZ inicializado.")


async def inicializar_agente_hibrido_app():
    global _agente_hibrido
    if _agente_hibrido is None:
        print("🚀 Inicializando agente HÍBRIDO (Voz -> Texto)...")
        from app.agents.agente_hibrido import AgenteHibridoJandula
        _agente_hibrido = AgenteHibridoJandula()
        await _agente_hibrido.inicializar()
        print("✅ Agente HÍBRIDO inicializado.")



# ==============================
# RUTA TEXTO
# ==============================

@router.post("/chat", response_model=ConsultaResponse)
async def consultar_agente(consulta: ConsultaRequest):

    if not consulta.pregunta.strip():
        raise HTTPException(status_code=400, detail="La pregunta no puede estar vacía")

    if _agente_grafo is None:
        await inicializar_agente_app()

    try:
        print(f"[API] Consulta texto: {consulta.pregunta}")

        config = {
            "configurable": {"thread_id": "default"}
        }

        # En la RUTA TEXTO o VOZ donde llames al grafo:
        respuesta = await asyncio.wait_for(
            _agente_grafo.ainvoke(
                {"messages": [("user", consulta.pregunta)]},
                {
                    "configurable": {"thread_id": "default"},
                    "recursion_limit": 25 
                }
            ),
            timeout=300
)

        mensajes = respuesta.get("messages", [])

        if mensajes:
            ultimo = mensajes[-1]
            if isinstance(ultimo, tuple):
                texto = ultimo[1]
            elif hasattr(ultimo, "content"):
                texto = str(ultimo.content)
            else:
                texto = str(ultimo)
        else:
            texto = "No se obtuvo respuesta del agente"

        return ConsultaResponse(respuesta=texto)

    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Timeout del agente")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ==============================
# RUTA VOZ
# ==============================

@router.post("/speak")
async def consultar_agente_voz(audio_file: UploadFile = File(...)):

    if _agente_voz is None:
        await inicializar_agente_voz_app()

    # 1️⃣ Guardar audio temporalmente
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        shutil.copyfileobj(audio_file.file, tmp)
        ruta_entrada = tmp.name

    try:
        print(f"[API] Procesando audio: {ruta_entrada}")

        # 🔥 interactuar ahora debe ser async
        ruta_salida = await asyncio.wait_for(
            _agente_voz.interactuar(ruta_entrada),
            timeout=300
        )

        if not os.path.exists(ruta_salida):
            raise HTTPException(status_code=500, detail="No se generó el audio de salida")

        return FileResponse(
            path=ruta_salida,
            media_type="audio/wav",
            filename="respuesta_jandula.wav"
        )

    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Timeout en proceso de voz")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en proceso de voz: {str(e)}")

    finally:
        if os.path.exists(ruta_entrada):
            os.remove(ruta_entrada)


# ==============================
# HEALTH
# ==============================

@router.get("/health")
async def health_check():
    return {"status": "ok", "servicio": "Agente IES Jándula"}



# ==============================
# RUTA HÍBRIDA: VOICE TO TEXT
# ==============================

@router.post("/transcribe")
async def consultar_agente_hibrido(audio_file: UploadFile = File(...)):
    """
    Recibe audio, transcribe y devuelve la respuesta del agente en texto.
    Ruta final: /api/agente/transcribe
    """
    if _agente_hibrido is None:
        await inicializar_agente_hibrido_app()

    # 1. Guardar audio temporalmente
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        shutil.copyfileobj(audio_file.file, tmp)
        ruta_entrada = tmp.name

    try:
        print(f"[API] Híbrido - Procesando audio: {ruta_entrada}")

        # 2. Llamada al método consultar del AgenteHibrido
        # Devuelve un dict con {"transcripcion_usuario": "...", "respuesta_agente": "..."}
        resultado = await asyncio.wait_for(
            _agente_hibrido.consultar(ruta_entrada),
            timeout=300
        )

        return resultado

    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Timeout en el proceso híbrido")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en agente híbrido: {str(e)}")
    
    finally:
        # 3. Limpieza del archivo temporal
        if os.path.exists(ruta_entrada):
            os.remove(ruta_entrada)