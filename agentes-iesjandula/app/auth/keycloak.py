"""
Verificación del JWT emitido por Keycloak.

Equivalente en Python de `libs/auth/src/jwt.strategy.ts` (vegaies):
  - firma verificada contra las claves públicas del realm (JWKS)
  - emisor (issuer) correcto y algoritmo RS256
No hay secreto compartido: la clave pública se descarga y se cachea de Keycloak.

El realm se toma de KEYCLOAK_ISSUER (config por despliegue, nada a fuego), que
debe ser EXACTAMENTE el mismo valor que usan core-data y accesos-api. Si diverge,
el token que sirve para Guardias no sirve aquí y el "un solo login" se rompe.
"""
import os
import threading

import jwt
from jwt import PyJWKClient

from .usuario import UsuarioAutenticado

ISSUER = os.getenv(
    "KEYCLOAK_ISSUER", "http://localhost:8080/realms/vegaies"
).rstrip("/")

JWKS_URI = f"{ISSUER}/protocol/openid-connect/certs"

#: Keycloak pone `aud: "account"` en los tokens de clientes públicos, así que
#: validar audiencia por defecto rechazaría tokens legítimos. vegaies tampoco la
#: valida. Si algún día se configura un audience mapper propio, basta con definir
#: KEYCLOAK_AUDIENCE y la comprobación se activa sola.
AUDIENCE = os.getenv("KEYCLOAK_AUDIENCE", "").strip() or None

_jwk_client: PyJWKClient | None = None
_lock = threading.Lock()


def _cliente_jwks() -> PyJWKClient:
    """Cliente JWKS perezoso y compartido (cachea las claves entre peticiones).

    Se crea a demanda y no al importar: si Keycloak todavía no está arriba
    cuando arranca el contenedor, la app debe seguir levantando y fallar solo
    en la primera petición autenticada, no en el import.
    """
    global _jwk_client
    if _jwk_client is None:
        with _lock:
            if _jwk_client is None:
                _jwk_client = PyJWKClient(
                    JWKS_URI,
                    cache_keys=True,
                    lifespan=300,       # refresca las claves cada 5 min
                    max_cached_keys=16,
                )
    return _jwk_client


class TokenInvalido(Exception):
    """El token falta, ha caducado o no valida. Se traduce a 401."""


def verificar_token(token: str) -> UsuarioAutenticado:
    """Valida el JWT y devuelve la identidad. Lanza TokenInvalido si no cuela.

    Es una función SÍNCRONA a propósito: `PyJWKClient` hace una petición HTTP
    bloqueante la primera vez, y FastAPI ejecuta las dependencias síncronas en
    su threadpool. Declararla `async` bloquearía el event loop entero mientras
    se descarga el JWKS.
    """
    try:
        clave = _cliente_jwks().get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            clave.key,
            algorithms=["RS256"],
            issuer=ISSUER,
            audience=AUDIENCE,
            options={
                "require": ["exp", "iss", "sub"],
                "verify_aud": AUDIENCE is not None,
            },
        )
    except Exception as e:
        raise TokenInvalido(str(e)) from e

    realm_access = payload.get("realm_access") or {}
    return UsuarioAutenticado(
        sub=payload["sub"],
        email=payload.get("email"),
        nombre=payload.get("name") or payload.get("preferred_username"),
        roles=list(realm_access.get("roles") or []),
    )
