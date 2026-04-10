import os
import shutil
import tempfile

from fastapi import UploadFile
from data.data import (
    subir_nuevo_documento,
    listar_documentos_en_coleccion,
    eliminar_documento_de_coleccion,
)

EXTENSIONES_PERMITIDAS = {".pdf", ".txt", ".md"}
PERFILES_VALIDOS = {"profesores", "alumnos"}


class RagService:

    @staticmethod
    def validar_perfil(perfil: str) -> bool:
        return perfil in PERFILES_VALIDOS

    async def procesar_subida(self, perfil: str, file: UploadFile) -> dict:
        """
        Guarda el archivo en un fichero temporal, lo procesa y lo inserta
        en la colección de ChromaDB correspondiente al perfil.
        El metadato 'source' en ChromaDB siempre reflejará el nombre
        original del archivo subido por el usuario, no la ruta temporal.
        """
        nombre_original = file.filename
        ext = os.path.splitext(nombre_original)[1].lower()

        if ext not in EXTENSIONES_PERMITIDAS:
            raise ValueError(
                f"Formato '{ext}' no soportado. "
                f"Formatos válidos: {', '.join(EXTENSIONES_PERMITIDAS)}"
            )

        # Creamos el fichero temporal con la extensión correcta para que
        # los loaders (PyPDFLoader, etc.) puedan identificar el tipo.
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            shutil.copyfileobj(file.file, tmp)
            temp_path = tmp.name

        try:
            resultado = subir_nuevo_documento(
                file_path=temp_path,
                perfil=perfil,
                nombre_original=nombre_original,   # ← nombre real para los metadatos
            )

            if resultado["status"] == "error":
                raise Exception(resultado["message"])

            return {
                "status": "success",
                "archivo": nombre_original,
                "perfil": perfil,
                "fragmentos": resultado.get("chunks", 0),
            }

        finally:
            # Limpieza garantizada aunque ocurra una excepción
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def listar_docs(self, perfil: str) -> dict:
        docs = listar_documentos_en_coleccion(perfil)
        return {"perfil": perfil, "documentos": docs, "total": len(docs)}

    def eliminar_doc(self, perfil: str, nombre_archivo: str) -> dict:
        return eliminar_documento_de_coleccion(perfil, nombre_archivo)


# Instancia singleton
rag_service = RagService()