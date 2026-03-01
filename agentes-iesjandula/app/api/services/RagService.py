import os
import shutil
from fastapi import UploadFile
from data.data import (
    subir_nuevo_documento, 
    listar_documentos_en_coleccion, 
    eliminar_documento_de_coleccion
)

class RagService:
    @staticmethod
    def validar_perfil(perfil: str):
        if perfil not in ["profesores", "alumnos"]:
            return False
        return True

    async def procesar_subida(self, perfil: str, file: UploadFile):
        # Validar extensión
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in [".pdf", ".txt", ".md"]:
            raise ValueError("Formato de archivo no soportado.")

        temp_path = f"temp_{file.filename}"
        
        # Guardar temporalmente para que la DB pueda leerlo
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        try:
            resultado = subir_nuevo_documento(temp_path, perfil)
            if resultado["status"] == "error":
                raise Exception(resultado["message"])
            
            return {
                "status": "success", 
                "archivo": file.filename, 
                "perfil": perfil,
                "fragmentos": resultado.get("chunks", 0)
            }
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def listar_docs(self, perfil: str):
        docs = listar_documentos_en_coleccion(perfil)
        return {"perfil": perfil, "documentos": docs, "total": len(docs)}

    def eliminar_doc(self, perfil: str, nombre_archivo: str):
        return eliminar_documento_de_coleccion(perfil, nombre_archivo)

# Instancia singleton
rag_service = RagService()