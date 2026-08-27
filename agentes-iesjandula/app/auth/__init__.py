"""
Autenticación y autorización del agente — un solo login (Keycloak) compartido
con el resto de aplicaciones del centro.

Mismo realm y mismos roles que vegaies (`libs/auth`): el token con el que un
profesor entra en Guardias o en Accesos vale aquí sin volver a identificarse.
"""
from .dependencias import requiere_admin, requiere_consulta, usuario_actual
from .roles import ROLES_ADMIN, ROLES_CONSULTA, es_admin
from .usuario import UsuarioAutenticado

__all__ = [
    "UsuarioAutenticado",
    "usuario_actual",
    "requiere_consulta",
    "requiere_admin",
    "ROLES_CONSULTA",
    "ROLES_ADMIN",
    "es_admin",
]
