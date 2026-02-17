"""
Rutas para consultar al agente de IES Jándula.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import asyncio
from concurrent.futures import ThreadPoolExecutor
from app.agents.agente_profesores import inicializar_agente_profesores

# Router para las rutas del agente
router = APIRouter(prefix="/agente", tags=["Agente"])

# Modelos de solicitud/respuesta
class ConsultaRequest(BaseModel):
    """Modelo para las consultas al agente."""
    pregunta: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "pregunta": "¿Cuál es el horario del IES Jándula?"
            }
        }

class ConsultaResponse(BaseModel):
    """Modelo para la respuesta del agente."""
    respuesta: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "respuesta": "El horario del IES Jándula es de 8:00 a 14:30..."
            }
        }

# Variables globales para el agente
_agente_grafo = None
_executor = ThreadPoolExecutor(max_workers=1)


def _ejecutar_agente_sync(pregunta: str):
    """Ejecuta el agente de forma sincrónica (sin threads internos de LangGraph)."""
    try:
        print(f"[API] Recibida consulta: {pregunta}")
        
        # Ejecutar con thread_id en configurable para memoria de conversación
        config = {
            "configurable": {"thread_id": "default"}
        }
        
        respuesta = _agente_grafo.invoke(
            {"messages": [("user", pregunta)]},
            config
        )
        
        # Extraer la respuesta
        mensajes = respuesta.get("messages", [])
        if mensajes:
            ultimo_mensaje = mensajes[-1]
            if isinstance(ultimo_mensaje, tuple):
                respuesta_texto = ultimo_mensaje[1]
            else:
                respuesta_texto = str(ultimo_mensaje.content) if hasattr(ultimo_mensaje, 'content') else str(ultimo_mensaje)
        else:
            respuesta_texto = "No se obtuvo respuesta del agente"
        
        print(f"[API] Respuesta generada: {respuesta_texto}")
        return respuesta_texto
        
    except Exception as e:
        print(f"[ERROR] Error en consulta al agente: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

async def inicializar_agente_app():
    """Inicia el agente al arrancar la app."""
    global _agente_grafo
    
    if _agente_grafo is None:
        print("🚀 Inicializando agente...")
        try:
            # Ejecutar inicialización en el executor para no bloquear el event loop
            _agente_grafo = await asyncio.get_event_loop().run_in_executor(
                _executor,
                inicializar_agente_profesores
            )
            print("✅ Agente inicializado correctamente.")
        except Exception as e:
            print(f"❌ Error al inicializar agente: {e}")
            raise RuntimeError(f"Error inicializando agente: {str(e)}")

@router.post("/consulta", response_model=ConsultaResponse)
async def consultar_agente(consulta: ConsultaRequest):
    """
    Consulta al agente del IES Jándula.
    
    Args:
        consulta: Objeto con la pregunta para el agente
        
    Returns:
        Respuesta del agente en formato JSON
        
    Raises:
        HTTPException: Si hay un error al procesar la consulta
    """
    try:
        if not consulta.pregunta.strip():
            raise HTTPException(status_code=400, detail="La pregunta no puede estar vacía")
        
        # Ejecutar el agente en el executor para no bloquear el event loop
        # Usa timeout de 300 segundos (5 minutos)
        resultado = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                _executor,
                _ejecutar_agente_sync,
                consulta.pregunta
            ),
            timeout=300
        )
        
        return ConsultaResponse(respuesta=resultado)
        
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Timeout: el agente tardó más de 5 minutos en responder")
    except Exception as e:
        print(f"[ERROR] Error en consulta: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al procesar la consulta: {str(e)}")

@router.get("/health")
async def health_check():
    """Verifica que el servicio está activo."""
    return {"status": "ok", "servicio": "Agente IES Jándula"}
