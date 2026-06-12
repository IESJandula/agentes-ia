import sys
import asyncio

# --- FIX PARA CHROMADB EN LINUX ---
# Redirige sqlite3 a pysqlite3 para evitar errores de versión en producción (Docker/Coolify)
if sys.platform.startswith("linux"):
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv


# ─────────────────────────────────────────────────────────────────────────────
# GZip selectivo: NUNCA comprimir respuestas SSE (text/event-stream).
# Comprimir un stream rompe el chunked-encoding sobre HTTP/2 y provoca
# ERR_HTTP2_PROTOCOL_ERROR en el navegador (el stream nunca llega).
# ─────────────────────────────────────────────────────────────────────────────
class SelectiveGZipMiddleware:
    def __init__(self, app, minimum_size: int = 500, exclude_paths: tuple = ()):
        self.app = app
        self.exclude_paths = exclude_paths
        self._gzip = GZipMiddleware(app, minimum_size=minimum_size)

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http" and any(
            scope.get("path", "").startswith(p) for p in self.exclude_paths
        ):
            await self.app(scope, receive, send)  # sin compresión
        else:
            await self._gzip(scope, receive, send)

from app.api.routes.AgentRoutes import router as agent_router
from app.api.routes.RagRoutes import router as rag_router
from app.api.routes.AdminRoutes import router as admin_router
from app.api.services.AgenteService import agents_service
from data.data import inicializar_bases_datos, seed_legislacion_folder

load_dotenv()

async def _seed_task():
    """Tarea en background: indexa documentos de data/legislacion/ al arrancar."""
    try:
        await asyncio.to_thread(seed_legislacion_folder)
    except Exception as e:
        print(f"⚠️ [SEED] Error en tarea de seed de legislación: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n" + "="*60)
    print("INICIANDO APLICACIÓN DEL AGENTE MULTIMODAL IES JÁNDULA")
    print("="*60)
    try:
        print("📊 Cargando/Verificando Bases de Datos RAG...")
        inicializar_bases_datos()

        print("📚 Lanzando seed de legislación en segundo plano...")
        asyncio.create_task(_seed_task())

        print("🚀 Inicializando Cerebro del Agente (Modo Texto/Profesores)...")
        await agents_service.procesar_chat("Hola", perfil="profesores")
        print("✅ Sistema listo para recibir consultas.")
    except Exception as e:
        print(f"⚠️ Nota: El pre-calentamiento falló, pero la app arrancará: {e}")

    yield
    print("\nFinalizando aplicación...")

# Crear aplicación FastAPI
app = FastAPI(
    title="Agente IES Jándula API",
    description="API para consultar al agente del IES Jándula",
    version="1.0.0",
    lifespan=lifespan
)

# Comprimir respuestas de texto (JSON, HTML) — ~70% menos ancho de banda.
# Se EXCLUYE /api/chat/stream porque comprimir SSE rompe el streaming HTTP/2.
app.add_middleware(
    SelectiveGZipMiddleware,
    minimum_size=500,
    exclude_paths=("/api/chat/stream",),
)

# Configurar CORS
# Nota: allow_origins=["*"] junto a allow_credentials=True es una combinación
# inválida según el spec CORS y los navegadores la rechazan. Como no usamos
# cookies/credenciales, dejamos "*" con credentials desactivado. Si en el futuro
# se necesitan credenciales, define CORS_ORIGINS con orígenes explícitos.
_cors_origins_env = os.getenv("CORS_ORIGINS", "").strip()
if _cors_origins_env:
    _allow_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
    _allow_credentials = True
else:
    _allow_origins = ["*"]
    _allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Incluir rutas con prefijos claros para evitar colisiones
app.include_router(agent_router, prefix="/api")
app.include_router(rag_router, prefix="/api")
app.include_router(admin_router, prefix="/api")

@app.get("/api")
async def api_root():
    """Endpoint raíz de la API."""
    return {
        "mensaje": "Bienvenido a la API del Agente IES Jándula",
        "docs": "/docs",
        "servicios": ["Agente Texto/Voz", "RAG"]
    }

# IMPORTANTE: Servimos la carpeta estática si existe (para JS, CSS, assets, etc.)
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def serve_index():
    """Sirve el frontend principal (index.html)."""
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {
        "mensaje": "Frontend no encontrado. Coloca tu archivo index.html en la raíz del proyecto.",
        "api_docs": "/docs"
    }

@app.get("/admin")
async def serve_admin():
    """Sirve el panel de administración."""
    if os.path.exists("admin.html"):
        return FileResponse("admin.html")
    return {"mensaje": "Panel de administración no encontrado."}

if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 8010))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
    )