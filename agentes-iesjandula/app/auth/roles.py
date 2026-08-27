"""
Reparto de roles del agente.

Vive aquí, en un solo sitio, y no repetido en cada router: la política de quién
puede qué es lo primero que hay que poder auditar de un vistazo. Es el mismo
criterio (y los mismos nombres de rol) que `libs/auth/src/roles-accesos.ts` en
vegaies, porque los reparte el mismo sync desde el Directorio: aquí no se
inventa ningún rol nuevo que luego hubiera que asignar a mano en Keycloak.

Dos niveles, no más:

  - CONSULTA: preguntar al agente. Lo concede `profesor`, igual que el puesto de
    accesos: en este centro cualquier docente puede consultar.

  - ADMINISTRACIÓN: gestionar la base de conocimiento (subir, borrar, priorizar)
    y ver las estadísticas de uso. `directiva` y `admin` conceden lo mismo.

Administración incluye consulta: quien cura los documentos también pregunta, y
separarlo obligaría a dos cuentas para la misma persona.
"""

#: Quién puede hablar con el agente.
ROLES_CONSULTA = ("profesor", "directiva", "admin")

#: Quién gestiona la base de conocimiento y ve las estadísticas.
ROLES_ADMIN = ("directiva", "admin")


def es_admin(roles: list[str]) -> bool:
    """¿Este usuario administra? Para las reglas que lo miran en runtime."""
    return any(r in ROLES_ADMIN for r in roles)
