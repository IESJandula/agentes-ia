from pydantic import BaseModel, Field

class ConsultaRequest(BaseModel):
    pregunta: str = Field(..., min_length=1, description="La pregunta para el agente")

class ConsultaResponse(BaseModel):
    respuesta: str