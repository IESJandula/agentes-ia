import os
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException
# Importamos solo lo que realmente usamos
from data.data import (
    subir_nuevo_documento, 
    listar_documentos_en_coleccion, 
    eliminar_documento_de_coleccion
)

router = APIRouter(prefix="/rag", tags=["RAG"])

def validar_perfil(perfil: str):
    if perfil not in ["profesores", "alumnos"]:
        raise HTTPException(status_code=400, detail="Perfil no válido.")

@router.post("/upload/{perfil}")
async def subir_documento(perfil: str, file: UploadFile = File(...)):
    validar_perfil(perfil)
    
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".pdf", ".txt", ".md"]:
        raise HTTPException(status_code=400, detail="Formato no soportado.")

    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # Usamos la función de alto nivel definida en data.py
        resultado = subir_nuevo_documento(temp_path, perfil)
        if resultado["status"] == "error":
            raise Exception(resultado["message"])
            
        return {
            "status": "success", 
            "archivo": file.filename, 
            "perfil": perfil,
            "fragmentos": resultado["chunks"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@router.get("/documents/{perfil}")
async def listar_documentos(perfil: str):
    validar_perfil(perfil)
    docs = listar_documentos_en_coleccion(perfil)
    return {"perfil": perfil, "documentos": docs, "total": len(docs)}

@router.delete("/documents/{perfil}/{nombre_archivo}")
async def borrar_documento(perfil: str, nombre_archivo: str):
    validar_perfil(perfil)
    resultado = eliminar_documento_de_coleccion(perfil, nombre_archivo)
    
    if resultado["status"] == "error":
        raise HTTPException(status_code=404, detail=resultado["message"])
        
    return resultado