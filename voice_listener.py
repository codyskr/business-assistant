import asyncio
import json
import os
import queue
import tempfile
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

SAMPLE_RATE = int(os.getenv("WAKE_SAMPLE_RATE", "16000"))
CHANNELS = 1
CHUNK_MS = int(os.getenv("WAKE_CHUNK_MS", "100"))
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_MS / 1000)
ENERGY_THRESHOLD = float(os.getenv("WAKE_ENERGY_THRESHOLD", "0.012"))
MIN_RECORD_SECONDS = float(os.getenv("WAKE_MIN_RECORD_SECONDS", "0.8"))
MAX_RECORD_SECONDS = float(os.getenv("WAKE_MAX_RECORD_SECONDS", "12"))
SILENCE_SECONDS = float(os.getenv("WAKE_SILENCE_SECONDS", "1.0"))
WAKE_WORDS = [
    word.strip().lower()
    for word in os.getenv("WAKE_WORDS", "ассистент,помощник").split(",")
    if word.strip()
]
LOCAL_COMMAND_URL = os.getenv("LOCAL_COMMAND_URL", "http://127.0.0.1:8765/command")
LOCAL_COMMAND_TOKEN = os.getenv("LOCAL_COMMAND_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("WAKE_TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_USER_ID = os.getenv("WAKE_TELEGRAM_USER_ID") or os.getenv("TELEGRAM_USER_ID", "")


def require_settings() -> None:
    missing = []
    if not TELEGRAM_CHAT_ID:
        missing.append("WAKE_TELEGRAM_CHAT_ID")
    if not TELEGRAM_USER_ID:
        missing.append("WAKE_TELEGRAM_USER_ID")
    if missing:
        raise RuntimeError(
            "Set these values in .env: "
            + ", ".join(missing)
            + ". Usually both can be your Telegram user id for a private chat."
        )


def import_audio_deps():
    try:
        import numpy as np
        import sounddevice as sd
    except ImportError as exc:
        raise RuntimeError(
            "Install microphone dependencies first: "
            "pip install -r voice_listener_requirements.txt"
        ) from exc
    return np, sd


def rms(np, chunk) -> float:
    if len(chunk) == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(chunk.astype("float32")))))


def write_wav(path: Path, frames: list[bytes]) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(CHANNELS)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(b"".join(frames))


async def transcribe_wav(path: Path) -> str:
    from bot import transcribe_with_local_whisper

    return (await transcribe_with_local_whisper(path)).strip()


def extract_command(text: str) -> str | None:
    lowered = text.lower().strip()
    for wake_word in WAKE_WORDS:
        index = lowered.find(wake_word)
        if index == -1:
            continue
        command = text[index + len(wake_word) :].strip(" ,.!?:;-—")
        return command or text.strip()
    return None


def post_command(text: str) -> None:
    payload = {
        "chat_id": int(TELEGRAM_CHAT_ID),
        "user_id": int(TELEGRAM_USER_ID),
        "text": text,
        "source": "laptop_wake_word",
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        LOCAL_COMMAND_URL,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    if LOCAL_COMMAND_TOKEN:
        request.add_header("Authorization", f"Bearer {LOCAL_COMMAND_TOKEN}")

    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            if response.status >= 300:
                raise RuntimeError(f"HTTP {response.status}: {response.read().decode('utf-8')}")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not send command to bot: {exc}") from exc


async def handle_recording(frames: list[bytes]) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        wav_path = Path(temp_dir) / "wake_command.wav"
        write_wav(wav_path, frames)
        text = await transcribe_wav(wav_path)

    if not text:
        return

    print(f"Recognized: {text}")
    command = extract_command(text)
    if not command:
        print(f"Ignored: wake word not found. Wake words: {', '.join(WAKE_WORDS)}")
        return

    print(f"Command: {command}")
    post_command(command)


def listen_forever() -> None:
    require_settings()
    np, sd = import_audio_deps()
    audio_queue: queue.Queue = queue.Queue()

    def callback(indata, frames, time_info, status) -> None:
        if status:
            print(status)
        audio_queue.put(indata.copy())

    print("Laptop voice listener started.")
    print(f"Wake words: {', '.join(WAKE_WORDS)}")
    print("Speak the wake word and command in one phrase.")

    recording = False
    frames: list[bytes] = []
    started_at = 0.0
    last_voice_at = 0.0

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        blocksize=CHUNK_SIZE,
        callback=callback,
    ):
        while True:
            chunk = audio_queue.get()
            energy = rms(np, chunk / 32768.0)
            now = time.monotonic()

            if energy >= ENERGY_THRESHOLD:
                if not recording:
                    recording = True
                    frames = []
                    started_at = now
                    print("Voice detected...")
                last_voice_at = now

            if recording:
                frames.append(chunk.tobytes())
                elapsed = now - started_at
                silence = now - last_voice_at
                if (
                    elapsed >= MIN_RECORD_SECONDS
                    and silence >= SILENCE_SECONDS
                ) or elapsed >= MAX_RECORD_SECONDS:
                    recording = False
                    try:
                        asyncio.run(handle_recording(frames))
                    except Exception as exc:
                        print(f"Recording handling failed: {exc}")
                    frames = []


if __name__ == "__main__":
    listen_forever()
