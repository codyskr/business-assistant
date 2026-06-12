# VK adapter

VK integration is an optional second messenger channel for the same organizer core.

Current scope:

- text messages from a VK community;
- `/help`, `/whoami`, `/reminders`, `/notes`, `/kb`, `/knowledge`;
- natural-language reminders and calendar actions through the same local parser;
- text confirmation: reply `подтвердить` or `отмена`;
- VK reminders are stored separately from Telegram reminders by using an internal id offset.

Not included yet:

- VK voice message transcription;
- VK document upload into the knowledge base;
- interactive VK buttons for selecting one item from many calendar/reminder matches.

## VK setup

1. Create or open a VK community.
2. Enable community messages.
3. Open community management, then API settings.
4. Create a community access token with message permissions.
5. Enable Long Poll API.
6. In Long Poll event types, enable incoming messages.
7. Put these values into `.env`:

```env
VK_GROUP_ID=123456789
VK_GROUP_TOKEN=vk1.a.your_token
ALLOWED_VK_USER_IDS=123456789
VK_API_VERSION=5.199
```

`VK_GROUP_ID` is the numeric community id without a minus sign.

`ALLOWED_VK_USER_IDS` is optional during first testing, but should be filled before real use. Send `/whoami` to the VK bot to see your VK user id.

## Run

Windows:

```powershell
.\start_bot.ps1 -RunVk
```

WSL:

```powershell
.\start_bot.ps1 -RunBotInWsl -RunVk
```

Direct Python run:

```bash
python vk_bot.py
```

## Usage

Examples:

```text
что ты умеешь
```

```text
напомни завтра в 10 забрать документы
```

```text
подтвердить
```

```text
/reminders завтра
```

```text
сделай заметку номер договора с Иваном 123
```

```text
найди заметку про договор с Иваном
```

Calendar actions use the same Google OAuth token storage as the main bot, but VK users are mapped to separate internal user ids. If calendar access is needed from VK, authorize that internal id from `/whoami`.
