# app/data/__init__.py

from .data import (
    profesores_col,
    alumnos_col,
    inicializar_bases_datos,
    subir_nuevo_documento,
    listar_documentos_en_coleccion,
    eliminar_documento_de_coleccion,
    obtener_coleccion
)
__all__ = [
    "profesores_col",
    "alumnos_col",
    "inicializar_bases_datos",
    "subir_nuevo_documento",
    "listar_documentos_en_coleccion",
    "eliminar_documento_de_coleccion",
    "obtener_coleccion"
]