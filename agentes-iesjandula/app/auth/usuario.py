"""Identidad autenticada extraída del JWT de Keycloak.

Espejo de `libs/auth/src/usuario.ts` de vegaies: mismo realm, mismo token y
por tanto la misma forma. Si allí se añade un campo, aquí también.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class UsuarioAutenticado:
    sub: str
    email: str | None = None
    nombre: str | None = None
    roles: list[str] = field(default_factory=list)
