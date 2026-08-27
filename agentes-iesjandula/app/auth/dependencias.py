"""
Dependencias de FastAPI para exigir sesión y rol.

Equivalen a `JwtAuthGuard` + `RolesGuard` de vegaies, pero al estilo de FastAPI:
se declaran por endpoint (o por router entero con `dependencies=[...]`).

Deny-by-default: aquí no hay ningún modo "sin auth". No existe un flag para
desactivar la autenticación en desarrollo a propósito — una variable de entorno
mal puesta en Dokploy volvería a dejar la base de conocimiento abierta a
cualquiera, que es justo el agujero que esto viene a cerrar. Para desarrollar,
apunta KEYCLOAK_ISSUER al Keycloak del centro.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .keycloak import TokenInvalido, verificar_token
from .roles import ROLES_ADMIN, ROLES_CONSULTA
from .usuario import UsuarioAutenticado

#: auto_error=False para poder devolver un 401 con nuestro propio mensaje en
#: castellano en lugar del "Not authenticated" genérico de FastAPI.
_bearer = HTTPBearer(auto_error=False)


def usuario_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UsuarioAutenticado:
    """Exige un JWT válido de Keycloak. Sin token válido → 401."""
    if credenciales is None or not credenciales.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token ausente o no válido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return verificar_token(credenciales.credentials)
    except TokenInvalido as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token ausente o no válido",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


def _exigir(roles_requeridos: tuple[str, ...]):
    """Fabrica una dependencia que exige uno de los roles indicados."""

    def dependencia(
        usuario: UsuarioAutenticado = Depends(usuario_actual),
    ) -> UsuarioAutenticado:
        if not any(r in roles_requeridos for r in usuario.roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requiere uno de estos roles: {', '.join(roles_requeridos)}",
            )
        return usuario

    return dependencia


#: Puede preguntar al agente (cualquier docente del centro).
requiere_consulta = _exigir(ROLES_CONSULTA)

#: Puede gestionar la base de conocimiento y ver estadísticas.
requiere_admin = _exigir(ROLES_ADMIN)
