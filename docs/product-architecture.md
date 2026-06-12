# Product architecture

The product should be sold as an assistant, not as a single messenger bot.

Target shape:

```text
Telegram adapter ─┐
VK adapter       ─┼─ assistant_core ─ calendar / reminders / notes / knowledge / LLM
Web/PWA adapter  ─┘
```

## Boundaries

Adapters should own:

- platform tokens and polling/webhook code;
- platform-specific ids;
- message sending;
- button or text confirmation UI;
- voice/file download from that platform.

The core should own:

- normalized user/channel identity;
- intent parsing;
- action execution;
- reminders;
- calendar operations;
- notes;
- knowledge base;
- memory;
- LLM/STT provider selection.

## Current first step

`assistant_core.ids` defines stable internal id ranges for each channel:

- Telegram keeps native ids for backward compatibility.
- VK uses a separate range to avoid mixing data with Telegram.
- Web and MAX ranges are reserved for future adapters.

This is not the final multi-tenant model. It is a safe compatibility bridge before adding real `users`, `workspaces`, and `channel_accounts` tables.

`assistant_core.commands` contains the first shared command handlers for platform-neutral text replies:

- help section resolution;
- reminders list replies;
- notes list/search replies;
- knowledge base list/search replies.

## Next refactor steps

1. Move text-response primitives into `assistant_core.messages`.
2. Move intent parsing and action execution behind one `AssistantCore.handle_text()` method.
3. Replace transport-specific pending confirmation code with a shared confirmation service.
4. Keep Telegram/VK/Web as thin adapters.
5. Add real user/workspace tables before selling to multiple clients.
