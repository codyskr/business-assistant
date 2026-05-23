# Local Telegram organizer agent

Локальный Telegram-бот для организационных задач:

- принимает текстовые и голосовые сообщения;
- распознает голос локально через `faster-whisper`;
- понимает намерение через локальную модель Ollama;
- создает события в Google Calendar после подтверждения;
- удаляет события из Google Calendar после поиска и подтверждения;
- переносит события в Google Calendar после поиска и подтверждения;
- ставит Telegram-напоминания и отправляет их в нужное время;
- хранит служебные данные в локальном SQLite.

Важно: анализ сообщения выполняется локально. Telegram и Google Calendar остаются облачными сервисами по своей природе: голосовое сообщение проходит через Telegram, а созданное событие отправляется в Google Calendar.

## 1. Подготовка Ollama

```bash
ollama pull llama3.2:3b
ollama serve
```

Проверка:

```bash
ollama run llama3.2:3b "Ответь одним словом: готов"
```

## 2. Установка зависимостей

```bash
pip install -r requirements.txt
```

Для голосовых сообщений на Windows/WSL может понадобиться `ffmpeg`.

## 3. Настройка Telegram

Создайте `.env` рядом с `bot.py`:

```env
TELEGRAM_BOT_TOKEN=ваш_токен_бота
ALLOWED_TELEGRAM_USER_IDS=123456789
OLLAMA_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2:3b
TIMEZONE=Europe/Moscow
WHISPER_MODEL=tiny
GOOGLE_CALENDAR_ID=primary
AUTO_CONFIRM_ACTIONS=false
DEFAULT_EVENT_REMINDER_MINUTES=15
MEMORY_ENABLED=true
MEMORY_KEY_PATH=data/memory.key
MEMORY_RETENTION_DAYS=7
MEMORY_RECENT_MESSAGES=12
MEMORY_RECENT_ACTIONS=6
```

`ALLOWED_TELEGRAM_USER_IDS` ограничивает доступ к боту. Свой Telegram user id можно узнать у `@userinfobot`. Можно оставить пустым на время теста.

Также можно написать боту:

```text
/whoami
```

Бот покажет ваш Telegram user id. Чтобы разрешить только себя, укажите:

```env
ALLOWED_TELEGRAM_USER_IDS=123456789
```

Несколько пользователей:

```env
ALLOWED_TELEGRAM_USER_IDS=123456789,987654321
```

## 4. Настройка Google Calendar

1. В Google Cloud Console создайте OAuth Client ID типа Desktop App.
2. Скачайте JSON.
3. Положите файл рядом с `bot.py` под именем `credentials.json`.

При первом создании события бот откроет OAuth-авторизацию. После входа локально появится `token.json`.

Можно заранее проверить интеграцию:

```bash
python google_calendar_setup.py
```

Создать тестовое событие:

```bash
python google_calendar_setup.py --create-test
```

## 5. Запуск

```bash
python bot.py
```

Windows PowerShell, одной командой:

```powershell
.\start_bot.ps1
```

Если Ollama и Python-окружение используются внутри WSL:

```powershell
.\start_bot.ps1 -RunBotInWsl
```

Примеры запросов:

```text
Создай встречу с Иваном завтра в 15:00 на час, напомни за 30 минут.
```

```text
Напомни мне сегодня в 21:30 проверить документы.
```

```text
Удали встречу с Иваном завтра.
```

```text
Удали все такие события каждый понедельник в 13 часов планерка отдела.
```

```text
Перенеси встречу с Иваном завтра на 17:00.
```

Если при удалении или переносе найдено несколько похожих событий, бот покажет кнопки выбора.

Поиск событий использует локальное ранжирование и fuzzy matching, поэтому лучше переносит опечатки и ошибки распознавания голоса.

Перед созданием события или напоминания бот покажет распознанное действие и попросит нажать `Подтвердить`.

Если хотите выполнять действия без кнопки подтверждения, поставьте:

```env
AUTO_CONFIRM_ACTIONS=true
```

Используйте это только после тестов: маленькая локальная модель может ошибиться в дате, времени или смысле просьбы.

После создания события бот отправляет summary: название, дату и время, место/подробности при наличии и время напоминания. Если пользователь не указал напоминание, используется `DEFAULT_EVENT_REMINDER_MINUTES=15`.

Правило разделения:

- `создай встречу/событие` — событие в Google Calendar;
- `напомни ...` — Telegram-напоминание;
- `каждый понедельник в 13:00 ...` без слов `создай встречу/событие` — серия Telegram-напоминаний каждую неделю;
- `создай встречу каждый понедельник в 13:00 ...` — серия событий в Google Calendar;
- `удали все такие события ...` или `удали всю серию ...` — удаление всех найденных совпадающих событий в Google Calendar;
- если сказано `напомни` и указано время события, но не указано отдельное время напоминания, бот напомнит за `DEFAULT_EVENT_REMINDER_MINUTES` минут до указанного времени.
- если для повторяющейся задачи не указан срок, бот создает серию на 365 дней вперед, максимум 60 штук.

## Локальная зашифрованная память

Бот сохраняет историю сообщений локально в SQLite (`data/agent.db`). Текст сообщений и история действий шифруются ключом Fernet из `data/memory.key`.

Команды:

```text
что ты умеешь
/memory
/forget_today
/today
/tomorrow
/week
/actions
/last
```

В модель передается не вся история, а короткая выжимка: последние сообщения и действия за период `MEMORY_RETENTION_DAYS`.

Календарные команды `/today`, `/tomorrow` и `/week` читают Google Calendar напрямую, без модели. `/actions` показывает последние локальные действия, `/last` — последнее действие.

## Приватность и ограничения

- LLM работает локально. STT может работать локально или через выбранный внешний сервис, если включен `PRIVACY_MODE=balanced`.
- SQLite-база находится в `data/agent.db`.
- Google OAuth-токен хранится локально в `token.json`.
- Бот не может написать человеку первым, если этот человек раньше не начинал чат с ботом.
- Для надежности все действия подтверждаются кнопкой.

## Бесплатное распознавание голоса

Бот умеет переключать STT-провайдеры без переписывания кода.

```env
PRIVACY_MODE=balanced
STT_PROVIDER=groq
STT_FALLBACK_PROVIDER=local
STT_MAX_VOICE_SECONDS=300
WHISPER_MODEL=base
GROQ_API_KEY=
GROQ_STT_MODEL=whisper-large-v3-turbo
```

- `PRIVACY_MODE=strict` — голос распознается только локально через `faster-whisper`.
- `PRIVACY_MODE=balanced` — сначала пробуется выбранный облачный STT, затем локальный fallback.
- `STT_PROVIDER=groq` — бесплатный/лимитированный Groq Whisper API.
- `STT_PROVIDER=local` — полностью локально, но качество зависит от модели `WHISPER_MODEL`.
- `/stt` — показать активную цепочку распознавания.
- `/privacy` — показать текущий режим приватности.
- `/help` — обзор функций и правил бота.
- `/help calendar`, `/help reminders`, `/help voice`, `/help memory` — разделы справки.
- `/debuglog` — последние 5 диагностических записей: вход, STT, intent, результат или ошибка.
- `/debuglog 10` — показать до 10 записей.
- `/reminders` — дела и Telegram-напоминания на сегодня.
- `/reminders завтра`, `/reminders послезавтра`, `/reminders 25.05.2026` — список на дату.

Для теста бесплатного Groq STT нужно получить ключ в Groq Console и вписать его в `.env`:

```env
GROQ_API_KEY=ваш_ключ
```
