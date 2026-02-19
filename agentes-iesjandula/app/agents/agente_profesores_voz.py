import torch
import os
import scipy.io.wavfile
from transformers import pipeline, VitsModel, AutoTokenizer
from .agente_profesores import inicializar_agente_profesores

class AgenteVozJandula:
    def __init__(self):
        # 1. El Cerebro
        self.grafo = inicializar_agente_profesores()
        
        # Determine dispositivo
        device_idx = 0 if torch.cuda.is_available() else -1
        
        # 2. El Oído (STT) - ¡Este está perfecto!
        self.stt_pipeline = pipeline(
            "automatic-speech-recognition",
            model="openai/whisper-tiny",
            device=device_idx
        )
        
        # 3. La Boca (TTS) - Usando el modelo de Facebook para español
        self.tts_model = VitsModel.from_pretrained("facebook/mms-tts-spa")
        self.tts_tokenizer = AutoTokenizer.from_pretrained("facebook/mms-tts-spa")
        
        if torch.cuda.is_available():
            self.tts_model.to("cuda")

    def procesar_audio_entrada(self, ruta_audio):
        res = self.stt_pipeline(ruta_audio)
        return res["text"]

    def generar_audio_salida(self, texto):
        """Genera audio real en español usando MMS-TTS."""
        inputs = self.tts_tokenizer(texto, return_tensors="pt")
        if torch.cuda.is_available():
            inputs = inputs.to("cuda")

        with torch.no_grad():
            output = self.tts_model(**inputs).waveform
        
        ruta_salida = "respuesta_jandula.wav"
        # Guardamos el audio usando scipy (formato wav estándar)
        scipy.io.wavfile.write(
            ruta_salida, 
            rate=self.tts_model.config.sampling_rate, 
            data=output.cpu().float().numpy().T
        )
        return ruta_salida

    def interactuar(self, archivo_usuario):
        texto_usuario = self.procesar_audio_entrada(archivo_usuario)
        print(f"👂 Transcripción: {texto_usuario}")
        
        config = {"configurable": {"thread_id": "audio_session_default"}}
        respuesta_grafo = self.grafo.invoke(
            {"messages": [("user", texto_usuario)]},
            config=config
        )
        
        ultimo_mensaje = respuesta_grafo["messages"][-1].content
        print(f"🤖 Respuesta texto: {ultimo_mensaje}")
        
        return self.generar_audio_salida(ultimo_mensaje)