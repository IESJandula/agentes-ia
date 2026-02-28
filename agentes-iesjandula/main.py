import sys
import asyncio
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from app.api.routes import router, inicializar_agente_app
from app.api.routes.rag_routes import router as rag_router
from app.api.routes import router, inicializar_agente_app
from data.data import inicializar_bases_datos



load_dotenv()

# Eventos de ciclo de vida de la aplicación
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Inicializar el agente cuando la app arranca
    print("\n" + "="*60)
    print("INICIANDO APLICACIÓN DEL AGENTE IES JÁNDULA")
    print("="*60)
    
    # 1. CARGAR LA BASE DE DATOS (RAG) PRIMERO
    print("🚀 CARGANDO BASE DE DATOS VECTORIAL...")
    inicializar_bases_datos() 
    
    # 2. INICIALIZAR EL AGENTE
    print("🚀 Inicializando agente texto...")
    await inicializar_agente_app()
    
    print("="*60 + "\n")
    yield
    # Shutdown
    print("\nAplicación finalizada.")

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

# Incluir rutas del agente
app.include_router(router, prefix="/api")
app.include_router(rag_router, prefix="/api")


@app.get("/")
async def root():
    """Endpoint raíz de bienvenida."""
    return {
        "mensaje": "Bienvenido a la API del Agente IES Jándula",
        "docs": "/docs",
        "endpoints": {
            "consulta": "/agente/consulta",
            "health": "/agente/health"
        }
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app", 
        host="127.0.0.1", 
        port=8000, 
        reload=False,
        timeout_keep_alive=300,  # 5 minutos para conexiones mantenidas vivas
        timeout_notify=300       # 5 minutos para notificaciones
    )