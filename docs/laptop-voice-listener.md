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
WAKE_TRANSCRIBE_PROVIDER=local
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
WAKE_TRANSCRIBE_PROVIDER=groq
WAKE_ENERGY_THRESHOLD=0.012
WAKE_MAX_RECORD_SECONDS=12
WAKE_SILENCE_SECONDS=1.0
WAKE_PHRASE_SILENCE_SECONDS=3.0
WAKE_COMMAND_DELAY_SECONDS=2.0
WAKE_COMMAND_MAX_SECONDS=12
```

`WAKE_TRANSCRIBE_PROVIDER=local` keeps recognition fully local.
`WAKE_TRANSCRIBE_PROVIDER=groq` sends only the recorded speech fragment after
local voice activity detection. It does not stream the microphone continuously.
`WAKE_TRANSCRIBE_PROVIDER=auto` tries Groq first and local Whisper if Groq fails.

Leave `WAKE_INPUT_DEVICE` empty for auto-detection. If the listener cannot open
the default microphone, set it to one of the input device indexes printed by the
diagnostic command or by the listener startup output.

Raise `WAKE_ENERGY_THRESHOLD` if it triggers on noise. Lower it if it misses
your voice.

Diagnostics:

```powershell
.\.venv\Scripts\python.exe voice_listener.py --list-devices
.\.venv\Scripts\python.exe voice_listener.py --meter 10
.\.venv\Scripts\python.exe voice_listener.py --record-test 5
.\.venv\Scripts\python.exe voice_listener.py --send-test "что ты умеешь"
```

`--meter` shows whether the microphone crosses `WAKE_ENERGY_THRESHOLD`.
`--record-test` saves a WAV file to `data/voice_debug` and prints the local
Whisper transcription. If the WAV is silent, the selected input device is wrong.
If the transcription is wrong, tune the microphone or local Whisper model.

To keep recordings for later inspection while running normally:

```env
WAKE_SAVE_RECORDINGS=true
WAKE_DEBUG_DIR=data/voice_debug
```

Two-step wake mode:

```text
джарвис
...pause about two seconds...
напомни завтра в 10 забрать документы
```

The first phrase is used only to detect the wake word. The command is recorded
after `WAKE_COMMAND_DELAY_SECONDS`, so the command itself does not need to
repeat the wake word.

In practice, because the listener only knows that you said the wake word after
speech-to-text finishes, the preferred mode is to keep the whole utterance in
one recording:

```text
джарвис
...pause up to WAKE_PHRASE_SILENCE_SECONDS...
сделай заметку Иван предпочитает созвоны после 14:00
```

Use `WAKE_PHRASE_SILENCE_SECONDS=3.0` so a two-second pause after the wake word
does not split the recording too early.
