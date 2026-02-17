# app/data/__init__.py

from .data import vector_store, inicializar_base_datos

# Esto permite que otros archivos vean estas variables fácilmente
__all__ = ["vector_store", "inicializar_base_datos"]