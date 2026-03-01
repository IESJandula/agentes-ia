import torch
import scipy.io.wavfile
from transformers import pipeline, VitsModel, AutoTokenizer

class MotorVoz:
    def __init__(self):
        device = 0 if torch.cuda.is_available() else -1
        #(STT)
        self.stt = pipeline("automatic-speech-recognition", model="openai/whisper-base", device=device)
        #(TTS)
        self.tts_model = VitsModel.from_pretrained("facebook/mms-tts-spa")
        self.tts_tokenizer = AutoTokenizer.from_pretrained("facebook/mms-tts-spa")
        if device == 0: self.tts_model.to("cuda")

    def escuchar(self, ruta):
        return self.stt(ruta, generate_kwargs={"language": "spanish"})["text"]

    def hablar(self, texto):
        inputs = self.tts_tokenizer(texto, return_tensors="pt")
        if torch.cuda.is_available(): inputs = inputs.to("cuda")
        with torch.no_grad():
            output = self.tts_model(**inputs).waveform
        ruta = "respuesta_jandula.wav"
        scipy.io.wavfile.write(ruta, rate=self.tts_model.config.sampling_rate, data=output.cpu().float().numpy().T)
        return ruta