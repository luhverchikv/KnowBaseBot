# voice_engine/recognizer.py

import os
import wave
import json
from vosk import Model, KaldiRecognizer
from .numbers import words_to_number

MODEL_PATH = "vosk-model-small-ru-0.22"

if not os.path.exists(MODEL_PATH):
    raise RuntimeError(f"Модель Vosk не найдена в {MODEL_PATH}")

vosk_model = Model(MODEL_PATH)


def recognize_text_from_wav(wav_path: str) -> str:
    """Возвращает распознанный текст из WAV."""
    wf = wave.open(wav_path, "rb")
    rec = KaldiRecognizer(vosk_model, wf.getframerate())
    rec.SetWords(True)
    text = ""

    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            text += " " + result.get("text", "")
    result = json.loads(rec.FinalResult())
    text += " " + result.get("text", "")
    return text.strip()


def recognize_number_from_text(text: str) -> int | None:
    """Пробует извлечь число из текста."""
    return words_to_number(text)
