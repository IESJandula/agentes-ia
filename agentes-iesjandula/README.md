# Agente IA — IES Jándula

Asistente del centro sobre FastAPI + LangGraph, con la documentación del
instituto indexada en ChromaDB (RAG) y búsqueda web como último recurso.

El acceso está cerrado: hace falta cuenta del centro. Es el mismo login que
Guardias y Accesos —el mismo Keycloak, el mismo realm y los mismos roles—, así
que quien ya ha entrado en cualquiera de ellas entra aquí sin pulsar nada.

---

## Quién puede hacer qué

| Rol de Keycloak | Puede |
|---|---|
| `profesor` | Preguntar al agente |
| `directiva`, `admin` | Además: gestionar la base de conocimiento y ver las estadísticas |

Los roles los reparte el sync desde el Directorio: aquí no se asigna ninguno a
mano. La lista vive en un solo sitio, [`app/auth/roles.py`](app/auth/roles.py).

No existe ningún modo "sin autenticación", ni una variable para desactivarla.
Para desarrollar, apunta `KEYCLOAK_ISSUER` al Keycloak del centro.

---

## La base de conocimiento

Cinco **categorías**, cada una una colección de ChromaDB con su propia tool:

| Categoría | Colección | Qué guarda |
|---|---|---|
| `centro` | `centro_info` | Oferta educativa, ciclos, servicios, trámites |
| `profesores` | `guia_profesorado` | Normativa interna, guardias, evaluación (no se ofrece al perfil de alumnado) |
| `alumnos` | `guia_alumnado` | Convivencia, horarios, actividades, becas |
| `legislacion` | `legislacion` | LOMLOE, decretos, currículos, BOE/BOJA |
| `conocimiento` | `conocimiento_web` | Lo que el agente ha indexado solo de sus búsquedas web |

### Prioridad: por categoría, no por documento

El agente prueba las categorías **en orden** y se queda con la primera que
responde; la web va siempre la última. Dentro de una categoría manda la
relevancia semántica, que para eso está.

Ese orden se cambia desde el panel (`/admin` → *Base de conocimiento* → *Orden
de consulta*) y afecta a dos cosas a la vez: en qué orden se le ofrecen las
tools al modelo y qué dice el bloque de prioridad del prompt. Se generan los dos
de la misma fuente para que no puedan contradecirse. Al guardar, los agentes en
memoria se descartan y se reconstruyen con la configuración nueva: no hace falta
redeploy.

---

## Añadir y quitar documentación

### Desde el panel (lo normal)

`/admin` → pestaña **Base de conocimiento**. Por cada categoría puedes:

- **Subir** PDF, TXT o MD. Se procesan y se indexan al momento; queda anotado
  quién los subió y cuándo.
- **Retirar** un documento. Deja de consultarse pero **no se borra**: es
  reversible y no cuesta reindexar. Es lo que quieres para un documento
  caducado.
- **Eliminar**. Borra sus fragmentos de ChromaDB. Recuperarlo obliga a
  reindexar el archivo entero, que con embeddings de cuota limitada no es
  gratis.

> Con embeddings de Gemini free tier (5 req/min), subir PDFs grandes consume
> cuota deprisa. Para lotes grandes, usa el seed con embeddings locales.

### Por carpeta (para lotes grandes)

Para cargas masivas que no quieres hacer a mano:

1. Deja los archivos en `data/centro/` o `data/legislacion/` y haz commit.
2. Pon `SEED_CENTRO=true` (o `SEED_LEGISLACION=true`) en las variables de
   entorno del despliegue.
3. Redeploy. En los logs verás `🏫 [SEED:CENTRO] …` o `📚 [SEED:LEGISLACION] …`.
4. **Vuelve a ponerlo en `false`** cuando termine.

El seed deduplica por nombre de archivo dentro de su colección: volver a
lanzarlo no reindexa lo que ya está.

> ⚠️ Comprueba que el volumen de `data/chroma_db_v3` es persistente en tu
> despliegue. Si no lo es, cada redeploy se lleva por delante todo lo subido
> desde el panel.

---

## Puesta en marcha

```bash
pip install -r requirements.txt
cp .env.example .env      # y rellena las claves
uvicorn main:app --port 8010
```

### Cliente de Keycloak

Una vez por despliegue, para crear el cliente público del frontal:

```bash
KEYCLOAK_URL=https://sso.tucentro.es AGENTES_ORIGIN=https://agente.tucentro.es bash infra/keycloak/configure-agentes-client.sh
```

Es idempotente y es el gemelo de los `configure-*-client.sh` de vegaies.

---

## Mapa del repositorio

```
app/
  auth/          Verificación del JWT de Keycloak y dependencias de rol
  agents/        Grafo LangGraph, configuración del modelo y prompts
  api/
    routes/      Endpoints (agente, RAG, admin)
    controllers/ Validación y traducción a HTTP
    services/    Lógica: agente, RAG, KbService (orden y estado de la KB)
  tools/         Una tool por categoría, más las de búsqueda web
data/
  data.py        ChromaDB: indexado, consulta, borrado y seeds
  centro/        Documentos del centro para el seed
  legislacion/   PDFs legislativos para el seed (no van en git)
static/
  auth.js        Sesión de Keycloak en el navegador
  vendor/        keycloak-js vendorizado (misma versión que vegaies)
index.html       Chat
admin.html       Panel de administración
```

---

## De dónde viene este repositorio

Es el continuador privado de [`IESJandula/agentes-ia`](https://github.com/IESJandula/agentes-ia),
el proyecto original. Se separó al añadir el login y el panel de administración:
a partir de aquí el repositorio guarda material del centro y estadísticas de uso
con el correo de quien pregunta, y eso no puede vivir en un repositorio público.

El original sigue ahí como `upstream`, y el intercambio va en los dos sentidos:

```bash
git fetch upstream && git merge upstream/main   # traer mejoras del original
```

Por eso el código sigue colgando de `agentes-iesjandula/` en vez de estar en la
raíz: mismas rutas que el original, así los cambios cruzan sin conflictos de
fichero. Lo genérico —arreglos del agente, prompts, indexado— se le devuelve al
original por PR. Lo del centro —documentos, estadísticas, el cliente de Keycloak
del realm de vegaies— se queda aquí.

### Qué no entra en git

Ni los PDFs del centro ni `data/chroma_db*/`. La sqlite de Chroma no guarda solo
vectores: lleva dentro el texto de los fragmentos, así que versionarla publica el
documento otra vez. Todo eso vive en el volumen del despliegue y se gestiona
desde el panel.
