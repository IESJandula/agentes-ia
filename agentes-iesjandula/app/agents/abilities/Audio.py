"""
Audio.py — IES Jándula
STT : Whisper medium   — mejor precisión en español que whisper-base
TTS : kokoro-onnx      — compatible con Python 3.13, sin espeak-ng, sin compilador C

Instalación:
    pip install kokoro-onnx soundfile torch transformers

Archivos de modelo necesarios (descargar una sola vez):
    onnx/model.onnx  →  https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX/tree/main/onnx
    voices/ef_dora.bin (u otra voz)  →  https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX/tree/main/voices

Coloca ambos archivos en el mismo directorio que este script,
o ajusta MODEL_PATH y VOICES_PATH a la ruta que prefieras.

Voces en español disponibles:
    ef_dora   — femenina (recomendada, la más natural)
    ef_bella  — femenina alternativa
    em_alex   — masculina
    em_santa  — masculina alternativa
"""

import torch
import numpy as np
import soundfile as sf
from pathlib import Path
from transformers import pipeline


# ── Rutas de los archivos ONNX ────────────────────────────────────────────────
_BASE_DIR   = Path(__file__).parent
MODEL_PATH  = _BASE_DIR / "kokoro-v1.0.onnx"
VOICES_PATH = _BASE_DIR / "voices-v1.0.bin"

LANG_CODE = "es"


class MotorVoz:
    def __init__(self,voz:str ="ef_dora", voz_path: Path = VOICES_PATH):
        self._device    = "cuda" if torch.cuda.is_available() else "cpu"
        self._voz    = voz
        self._voz_path  = Path(voz_path)
        self._stt       = None
        self._tts       = None

    # ── Carga perezosa ────────────────────────────────────────────────────────

    def _cargar_stt(self):
        if self._stt is not None:
            return
        print("Cargando Whisper medium...")
        self._stt = pipeline(
            "automatic-speech-recognition",
            model="openai/whisper-medium",
            device=0 if self._device == "cuda" else -1,
            generate_kwargs={"language": "spanish", "task": "transcribe"},
            chunk_length_s=30,
            stride_length_s=5,
        )
        print("STT listo.")

    def _cargar_tts(self):
        if self._tts is not None:
            return

        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Falta el modelo Kokoro.\n"
                f"Descarga 'model.onnx' desde:\n"
                f"  https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX/tree/main/onnx\n"
                f"y colócalo en: '{_BASE_DIR}'"
            )
        if not self._voz_path.exists():
            raise FileNotFoundError(
                f"Falta el archivo de voz '{self._voz_path.name}'.\n"
                f"Descárgalo desde:\n"
                f"  https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX/tree/main/voices\n"
                f"y colócalo en: '{_BASE_DIR}'"
            )

        print("Cargando Kokoro ONNX...")
        from kokoro_onnx import Kokoro
        self._tts = Kokoro(str(MODEL_PATH), str(self._voz_path))
        print("TTS listo.")

    # ── API pública ───────────────────────────────────────────────────────────

    def escuchar(self, ruta: str) -> str:
        """
        Transcribe un archivo de audio a texto en español.

        Args:
            ruta: ruta al archivo (.wav, .mp3, .ogg, .m4a)

        Returns:
            Texto transcrito.
        """
        self._cargar_stt()
        resultado = self._stt(ruta)
        texto = resultado["text"].strip()
        print(f"Transcrito: {texto}")
        return texto

    def hablar(self, texto: str, ruta_salida: str = "respuesta_jandula.wav") -> str:
        """
        Convierte texto a voz en español y guarda el resultado en WAV.

        Args:
            texto:       Texto a sintetizar.
            ruta_salida: Ruta del archivo WAV de salida.

        Returns:
            Ruta del archivo WAV generado.
        """
        self._cargar_tts()

        samples, sample_rate = self._tts.create(
            texto,
            voice=self._voz,
            speed=0.95,     # ligeramente más lento suena más natural en español
            lang=LANG_CODE,
        )

        sf.write(ruta_salida, samples, sample_rate)
        print(f"Audio guardado en: {ruta_salida}")
        return ruta_salida

    async def hablar_async(self, texto: str, ruta_salida: str = "respuesta_jandula.wav") -> str:
        """
        Versión async para textos largos — genera por fragmentos.
        Usar dentro de endpoints FastAPI en vez de hablar().
        """
        self._cargar_tts()

        fragmentos = []
        sample_rate_final = 24000

        async for samples, sample_rate in self._tts.create_stream(
            texto,
            voice=self._voz,
            speed=0.95,
            lang=LANG_CODE,
        ):
            fragmentos.append(samples)
            sample_rate_final = sample_rate

        if not fragmentos:
            raise RuntimeError("Kokoro no generó audio.")

        audio_final = np.concatenate(fragmentos)
        sf.write(ruta_salida, audio_final, sample_rate_final)
        print(f"Audio (stream) guardado en: {ruta_salida}")
        return ruta_salida