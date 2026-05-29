import os
import shutil
import tempfile

from fastapi import UploadFile
from typing import List
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

    async def _procesar_un_archivo(self, perfil: str, file: UploadFile) -> dict:
        """
        Guarda un archivo en un fichero temporal, lo procesa y lo inserta
        en la colección de ChromaDB correspondiente al perfil.
        El metadato 'source' en ChromaDB siempre reflejará el nombre
        original del archivo subido por el usuario, no la ruta temporal.
        """
        nombre_original = file.filename
        ext = os.path.splitext(nombre_original)[1].lower()

        if ext not in EXTENSIONES_PERMITIDAS:
            return {
                "status": "error",
                "archivo": nombre_original,
                "message": (
                    f"Formato '{ext}' no soportado. "
                    f"Formatos válidos: {', '.join(EXTENSIONES_PERMITIDAS)}"
                ),
            }

        # Creamos el fichero temporal con la extensión correcta para que
        # los loaders (PyPDFLoader, etc.) puedan identificar el tipo.
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            shutil.copyfileobj(file.file, tmp)
            temp_path = tmp.name

        try:
            resultado = subir_nuevo_documento(
                file_path=temp_path,
                perfil=perfil,
                nombre_original=nombre_original,
            )

            if resultado["status"] == "error":
                return {
                    "status": "error",
                    "archivo": nombre_original,
                    "message": resultado["message"],
                }

            return {
                "status": "success",
                "archivo": nombre_original,
                "fragmentos": resultado.get("chunks", 0),
            }

        except Exception as e:
            return {
                "status": "error",
                "archivo": nombre_original,
                "message": str(e),
            }

        finally:
            # Limpieza garantizada aunque ocurra una excepción
            if os.path.exists(temp_path):
                os.remove(temp_path)

    async def procesar_subida_multiple(self, perfil: str, files: List[UploadFile]) -> dict:
        """
        Procesa y sube múltiples archivos al RAG de forma secuencial,
        devolviendo un resumen con el resultado de cada uno.
        """
        resultados = []
        for file in files:
            resultado = await self._procesar_un_archivo(perfil, file)
            resultados.append(resultado)

        exitosos = [r for r in resultados if r["status"] == "success"]
        fallidos = [r for r in resultados if r["status"] == "error"]

        return {
            "perfil": perfil,
            "total": len(resultados),
            "exitosos": len(exitosos),
            "fallidos": len(fallidos),
            "resultados": resultados,
        }

    def listar_docs(self, perfil: str) -> dict:
        docs = listar_documentos_en_coleccion(perfil)
        return {"perfil": perfil, "documentos": docs, "total": len(docs)}

    def eliminar_doc(self, perfil: str, nombre_archivo: str) -> dict:
        return eliminar_documento_de_coleccion(perfil, nombre_archivo)


# Instancia singleton
rag_service = RagService()