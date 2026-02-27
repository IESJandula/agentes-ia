import torch
from transformers import pipeline
from .agente_profesores import inicializar_agente_profesores

class AgenteHibridoJandula:
    """
    Agente que recibe un archivo de audio, lo transcribe y 
    devuelve la respuesta del modelo en formato texto.
    """

    def __init__(self):
        # 1. Configuración de Hardware
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        device_idx = 0 if torch.cuda.is_available() else -1

        # 2. Oído (STT - Speech to Text)
        # Usamos Whisper para transcribir el audio del usuario
        self.stt_pipeline = pipeline(
            "automatic-speech-recognition",
            model="openai/whisper-tiny",
            device=device_idx
        )
        
        self.grafo = None

    async def inicializar(self):
        """
        Inicializa el grafo de LangGraph. 
        Nota: Usamos es_voz=False para que el LLM pueda devolver 
        listas o formato Markdown si es necesario en el texto.
        """
        self.grafo = await inicializar_agente_profesores(es_voz=False)

    def transcribir_audio(self, ruta_audio):
        """Convierte el archivo de audio en texto."""
        print(f"🎤 Procesando audio: {ruta_audio}")
        resultado = self.stt_pipeline(ruta_audio)
        return resultado["text"]

    async def consultar(self, ruta_audio_usuario):
        """
        Flujo Híbrido:
        1. Recibe Audio -> 2. Transcribe a Texto -> 3. Procesa en Grafo -> 4. Devuelve Texto
        """
        # Paso 1 y 2: De Voz a Texto
        texto_usuario = self.transcribir_audio(ruta_audio_usuario)
        print(f"📝 Usuario dijo: {texto_usuario}")

        # Paso 3: Interacción con el Agente (LangGraph)
        config = {"configurable": {"thread_id": "hibrido_session_123"}}
        
        # Invocamos al grafo con el texto transcrito
        eventos = await self.grafo.ainvoke(
            {"messages": [("user", texto_usuario)]},
            config
        )

        # Paso 4: Extraer el contenido del último mensaje (la respuesta del asistente)
        respuesta_texto = eventos["messages"][-1].content
        
        return {
            "transcripcion_usuario": texto_usuario,
            "respuesta_agente": respuesta_texto
        }

# Ejemplo de uso (pseudocódigo):
# agente = AgenteHibridoJandula()
# await agente.inicializar()
# resultado = await agente.consultar("pregunta_profesor.wav")
# print(resultado["respuesta_agente"])