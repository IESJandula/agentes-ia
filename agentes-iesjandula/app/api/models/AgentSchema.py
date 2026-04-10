from pydantic import BaseModel, Field
from typing import Optional

class ConsultaRequest(BaseModel):
    pregunta:  str            = Field(..., min_length=1, description="La pregunta para el agente")
    perfil:    str            = Field("profesores", description="Perfil del usuario: 'profesores' | 'alumnos'")
    thread_id: Optional[str]  = Field(None, description="ID de sesión para mantener el historial de conversación")

class ConsultaResponse(BaseModel):
    respuesta: str