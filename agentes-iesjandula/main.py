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
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from app.api.routes.AgentRoutes import router as agent_router
from app.api.routes.RagRoutes import router as rag_router
from app.api.services.AgenteService import agents_service  
from data.data import inicializar_bases_datos

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n" + "="*60)
    print("INICIANDO APLICACIÓN DEL AGENTE MULTIMODAL IES JÁNDULA")
    print("="*60)
    try:
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

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Incluir rutas con prefijos claros para evitar colisiones
app.include_router(agent_router, prefix="/api")
app.include_router(rag_router, prefix="/api")

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

if __name__ == "__main__":
    uvicorn.run(
        "main:app", 
        host="127.0.0.1", 
        port=8000, 
        reload=True,
        timeout_keep_alive=300,
        timeout_notify=300
    )