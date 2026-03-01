from pydantic import BaseModel
from typing import List

class DocumentoInfo(BaseModel):
    archivo: str
    perfil: str
    fragmentos: int

class ListaDocumentosResponse(BaseModel):
    perfil: str
    documentos: List[str]
    total: int