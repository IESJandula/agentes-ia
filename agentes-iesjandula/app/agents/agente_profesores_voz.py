import torch
import scipy.io.wavfile
import os
from transformers import pipeline, VitsModel, AutoTokenizer
from .agente_profesores import inicializar_agente_profesores

class AgenteVozJandula:

    def __init__(self):
        self.grafo = None
        device_idx = 0 if torch.cuda.is_available() else -1

        # 2. Oído (STT) - FORZAMOS ESPAÑOL AQUÍ TAMBIÉN POR SEGURIDAD
        self.stt_pipeline = pipeline(
            "automatic-speech-recognition",
            model="openai/whisper-base",
            device=device_idx
        )

        # 3. Boca (TTS)
        self.tts_model = VitsModel.from_pretrained("facebook/mms-tts-spa")
        self.tts_tokenizer = AutoTokenizer.from_pretrained("facebook/mms-tts-spa")

        if torch.cuda.is_available():
            self.tts_model.to("cuda")

    async def inicializar(self):
        self.grafo = await inicializar_agente_profesores(es_voz=True)

    def procesar_audio_entrada(self, ruta_audio):
        # 🔥 CAMBIO CLAVE: Forzamos el decoder a español en cada llamada
        # para evitar que Whisper "alucine" con el griego en audios cortos.
        res = self.stt_pipeline(
            ruta_audio, 
            generate_kwargs={"language": "spanish", "task": "transcribe"}
        )
        return res["text"]

    def generar_audio_salida(self, texto):
        inputs = self.tts_tokenizer(texto, return_tensors="pt")
        if torch.cuda.is_available():
            inputs = inputs.to("cuda")
        
        with torch.no_grad():
            output = self.tts_model(**inputs).waveform
        
        ruta_salida = "respuesta_jandula.wav"
        # Normalizamos el audio para que scipy no de problemas
        audio_data = output.cpu().float().numpy().T
        scipy.io.wavfile.write(
            ruta_salida,
            rate=self.tts_model.config.sampling_rate,
            data=audio_data
        )
        return ruta_salida

    async def interactuar(self, archivo_usuario):
        # 1. Transcribir
        texto_usuario = self.procesar_audio_entrada(archivo_usuario)
        print(f"👂 Transcripción: {texto_usuario}")

        # 2. Configurar el grafo con RECURSION_LIMIT
        # 🔥 CAMBIO CLAVE: Añadimos recursion_limit para evitar bucles infinitos
        config = {
            "configurable": {"thread_id": "audio_session_default"},
            "recursion_limit": 10  # Máximo 10 pasos (nodos) por consulta
        }

        try:
            respuesta_grafo = await self.grafo.ainvoke(
                {"messages": [("user", texto_usuario)]},
                config
            )

            ultimo_mensaje = respuesta_grafo["messages"][-1].content
            print(f"🤖 Respuesta texto: {ultimo_mensaje}")
            
            return self.generar_audio_salida(ultimo_mensaje)

        except Exception as e:
            # Si el agente se pierde buscando, damos una respuesta controlada
            error_msg = "Lo siento, he buscado en los registros pero no he encontrado una respuesta clara. ¿Puedes repetir?"
            if "recursion_limit" in str(e).lower():
                print("⚠️ Límite de recursión alcanzado (bucle de herramientas).")
            else:
                print(f"❌ Error en el grafo: {e}")
            
            return self.generar_audio_salida(error_msg)