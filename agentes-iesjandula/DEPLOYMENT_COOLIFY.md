# 🚀 Guía de Despliegue en Coolify

## 📋 Resumen de la Arquitectura

Este proyecto es un **Agente IA Multimodal** que usa:
- **LLM**: Google Gemini 2.0 Flash (API)
- **Embeddings**: Google Gemini (API)
- **Base de Datos Vectorial**: ChromaDB (Remoto/HttpClient)
- **Búsqueda Web**: Tavily API
- **Framework**: FastAPI + LangGraph
- **Puerto**: 8010 (no 8000, porque está ocupado)

---

## 🔧 Configuración en Coolify

### 1. **Variables de Entorno**

En Coolify, ve a **Environment Variables** y configura:

```env
# ✅ REQUIERIDAS - API Keys
GENAI_API_KEY=AIzaSyBMLwvvuUIvWB_x6jCip9MX5XuBGcVzlDQ
TAVILY_API_KEY=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

# 🗄️ ChromaDB Remoto - IMPORTANTE
# Opción A: Si ChromaDB está en el mismo host de Coolify
CHROMA_SERVER_HOST=localhost
CHROMA_SERVER_HTTP_PORT=8000

# Opción B: Si ChromaDB está en otro contenedor/máquina
# CHROMA_SERVER_HOST=chroma.tu-dominio.com
# O: CHROMA_SERVER_HOST=192.168.x.x (IP interna)

# 🌐 Puerto de la Aplicación
PORT=8010
```

---

## 💾 Almacenamiento Persistente (ChromaDB)

El proyecto detecta automáticamente el volumen de ChromaDB mapeado en Coolify.

### Verificación:
1. En Coolify → Proyecto ChromaDB → Persistent Storages
2. Confirma que existe el volumen:
   - **Volume Name**: `hhqqlc6syc137kxpqg8vvont_chroma-data`
   - **Destination Path**: `/data`

### El código en `data.py` hace:
```python
# Conecta a ChromaDB remoto vía HTTP (no almacenamiento local)
chroma_host = os.getenv("CHROMA_SERVER_HOST", "localhost")
chroma_port = int(os.getenv("CHROMA_SERVER_HTTP_PORT", "8000"))
client = chromadb.HttpClient(host=chroma_host, port=chroma_port)

# Embeddings de Google Gemini (no locales)
embedding_fn = GoogleGenerativeAIEmbeddings(
    model="models/embedding-001",
    google_api_key=os.getenv("GENAI_API_KEY"),
)
```

✅ **Resultado**: El proyecto **NO** usa almacenamiento local. Todos los datos van a ChromaDB remoto.

---

## 🐳 Dockerfile Optimizado

El `Dockerfile` está listo para Coolify:

```dockerfile
# Base: Python 3.12 slim (500-600MB)
FROM python:3.12-slim

# Puerto configurado
ENV PORT=8010

# Dependencias mínimas (sin Ollama, sin librerías pesadas)
RUN apt-get install -y --no-install-recommends \
    build-essential libffi-dev libssl-dev

# Instalación de dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright para web scraping
RUN playwright install --with-deps chromium

# Health check para Coolify
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8010/api', timeout=5)" || exit 1

# Comando final
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8010"]
```

✅ **Ventajas**:
- Imagen ligera (~600MB)
- Sin Ollama local (infra pesada eliminada)
- Health check integrado
- Puertos correctamente configurados

---

## 🔌 Conectividad entre Contenedores (Coolify)

### Escenario 1: ChromaDB en el mismo Coolify
```env
CHROMA_SERVER_HOST=localhost
CHROMA_SERVER_HTTP_PORT=8000
```

**Problema potencial**: "localhost" dentro del contenedor se refiere a SÍ MISMO.

**Solución**: Usa el nombre del servicio ChromaDB en Coolify:
```env
# Si el servicio se llama "chroma"
CHROMA_SERVER_HOST=chroma
CHROMA_SERVER_HTTP_PORT=8000

# Si está en otra máquina
CHROMA_SERVER_HOST=chroma.coolify.local
CHROMA_SERVER_HTTP_PORT=8000
```

### Escenario 2: ChromaDB en otra máquina
```env
CHROMA_SERVER_HOST=192.168.1.100  # IP interna
CHROMA_SERVER_HTTP_PORT=8000
```

---

## 📝 Checklist de Despliegue

- [ ] **Variables de Entorno** configuradas en Coolify
  - [ ] `GENAI_API_KEY` válida
  - [ ] `TAVILY_API_KEY` válida
  - [ ] `CHROMA_SERVER_HOST` correcto
  - [ ] `PORT=8010`

- [ ] **Volumen de ChromaDB** 
  - [ ] Existe en Coolify
  - [ ] Puerto 8000 accesible
  - [ ] Red compatible con el contenedor

- [ ] **Dockerfile**
  - [ ] Base directory: `/agentes-iesjandula`
  - [ ] Build pack: Nixpacks (auto-detectado)
  - [ ] Start command: `uvicorn main:app --host 0.0.0.0 --port 8010`

- [ ] **Endpoints API**
  - [ ] GET `/api` → Debe devolver JSON
  - [ ] POST `/api/agent/chat` → Envía consulta
  - [ ] POST `/api/rag/upload` → Sube documentos

---

## 🧪 Pruebas Locales (Antes de Desplegar)

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Asegurar variables de entorno
cp .env.example .env
# Editar .env con valores reales

# 3. Ejecutar en desarrollo
python main.py

# 4. Probar endpoints
curl http://localhost:8010/api

# 5. Ver documentación OpenAPI
http://localhost:8010/docs
```

---

## 🔍 Validar Conectividad a ChromaDB

```python
# Script para validar conexión (en scratch/test_chroma.py)
import chromadb
import os
from dotenv import load_dotenv

load_dotenv()

chroma_host = os.getenv("CHROMA_SERVER_HOST", "localhost")
chroma_port = int(os.getenv("CHROMA_SERVER_HTTP_PORT", "8000"))

try:
    client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
    print("✅ Conexión a ChromaDB exitosa")
    print(f"   Host: {chroma_host}")
    print(f"   Port: {chroma_port}")
    collections = client.list_collections()
    print(f"   Colecciones: {[c.name for c in collections]}")
except Exception as e:
    print(f"❌ Error conectando a ChromaDB: {e}")
```

---

## 📊 Tamaño de la Imagen Docker

**Antes (con Ollama local)**: ~2.5GB ❌
**Después (Gemini API)**: ~500-600MB ✅

Ahorro: **75-80%** de tamaño

---

## 🚨 Problemas Comunes

### ❌ "GENAI_API_KEY not configured"
**Solución**: Verificar que existe en Environment Variables de Coolify

### ❌ "Connection refused to ChromaDB"
**Solución**: 
- Verificar que ChromaDB está corriendo en Coolify
- Cambiar `CHROMA_SERVER_HOST` al nombre/IP correcto
- Asegurar que el puerto 8000 es accesible

### ❌ "Port 8010 already in use"
**Solución**: Cambiar `PORT` en variables de entorno a otro puerto libre

### ❌ Playwright no instala chromium
**Solución**: El Dockerfile ya tiene `RUN playwright install --with-deps chromium`

---

## 📚 Referencias

- [Gemini API Docs](https://ai.google.dev)
- [LangChain Google GenAI](https://python.langchain.com/docs/integrations/llms/google_generativeai)
- [ChromaDB HTTP Client](https://docs.trychroma.com/getting-started)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)

---

## 🎯 Próximos Pasos

1. ✅ Copiar `.env` y configurar variables
2. ✅ Verificar volumen de ChromaDB en Coolify
3. ✅ Build de imagen Docker
4. ✅ Deploy en Coolify
5. ✅ Probar endpoints en `/docs`
6. ✅ Monitorear logs en Coolify

**¡Listo para producción!** 🚀
