# Laptop voice listener

This mode keeps microphone listening local on the laptop. Groq is not used for
continuous listening.

Flow:

```text
microphone -> local speech detection -> local faster-whisper transcription
-> local bot HTTP endpoint -> normal bot intent handling
```

Enable the local command endpoint in `.env`:

```env
LOCAL_COMMAND_ENABLED=true
LOCAL_COMMAND_HOST=127.0.0.1
LOCAL_COMMAND_PORT=8765
LOCAL_COMMAND_TOKEN=change_me
LOCAL_COMMAND_URL=http://127.0.0.1:8765/command
WAKE_WORDS=ассистент,помощник
WAKE_INPUT_DEVICE=
WAKE_TELEGRAM_CHAT_ID=123456789
WAKE_TELEGRAM_USER_ID=123456789
```

For a private Telegram chat, `WAKE_TELEGRAM_CHAT_ID` and
`WAKE_TELEGRAM_USER_ID` are usually the same id shown by `/whoami`.

Install microphone dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r voice_listener_requirements.txt
```

Start bot and listener:

```powershell
.\start_bot.ps1 -VoiceListen
```

If the bot runs in WSL but microphone is on Windows:

```powershell
.\start_bot.ps1 -RunBotInWsl -VoiceListen
```

Say the wake word and command in one phrase:

```text
ассистент напомни завтра в 10 забрать документы
```

Tuning:

```env
WAKE_INPUT_DEVICE=26
WAKE_ENERGY_THRESHOLD=0.012
WAKE_MAX_RECORD_SECONDS=12
WAKE_SILENCE_SECONDS=1.0
```

Leave `WAKE_INPUT_DEVICE` empty for auto-detection. If the listener cannot open
the default microphone, set it to one of the input device indexes printed by the
diagnostic command or by the listener startup output.

Raise `WAKE_ENERGY_THRESHOLD` if it triggers on noise. Lower it if it misses
your voice.
