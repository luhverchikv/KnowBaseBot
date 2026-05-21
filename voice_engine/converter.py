# voice_engine/converter.py
import subprocess

async def ogg_to_wav(ogg_path: str, wav_path: str):
    """Конвертирует OGG (opus) -> WAV 16kHz mono"""
    cmd = [
        "ffmpeg", "-y",
        "-i", ogg_path,
        "-ar", "16000",
        "-ac", "1",
        wav_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
