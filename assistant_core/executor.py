from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ActionExecutorDeps:
    store: Any
    safe_reply_text: Callable[..., Awaitable[bool]]
    format_msk_dt: Callable[[str], str]
    calendar_event_summary: Callable[[dict[str, Any], str], str]
    calendar_event_label: Callable[[dict[str, Any]], str]
    create_calendar_event: Callable[..., Awaitable[str]]
    create_calendar_event_from_fields: Callable[..., Awaitable[str]]
    find_calendar_events: Callable[..., Awaitable[list[dict[str, Any]]]]
    find_calendar_events_limited: Callable[..., Awaitable[list[dict[str, Any]]]]
    delete_calendar_event_by_id: Callable[..., Awaitable[None]]
    reschedule_calendar_event_by_payload: Callable[..., Awaitable[dict[str, Any]]]
    schedule_reminder: Callable[..., Awaitable[None]]
    export_reminders_markdown: Callable[[int], Any]
    ask_user_to_select_event: Callable[..., Awaitable[None]]
    execute_delete_reminders: Callable[..., Awaitable[None]]


async def execute_action(
    parsed: dict[str, Any],
    *,
    chat_id: int,
    user_id: int | None,
    app: Any,
    reply_target: Any,
    deps: ActionExecutorDeps,
) -> None:
    try:
        if parsed["kind"] == "calendar_event":
            link = await deps.create_calendar_event(parsed, user_id=user_id)
            await deps.safe_reply_text(reply_target, deps.calendar_event_summary(parsed, link))
        elif parsed["kind"] == "reminder":
            reminder = parsed["reminder"]
            reminder_id = deps.store.add_reminder(
                chat_id=chat_id,
                text=reminder["text"],
                remind_at=reminder["remind_at"],
            )
            await deps.schedule_reminder(
                app,
                reminder_id,
                chat_id,
                reminder["text"],
                reminder["remind_at"],
            )
            deps.export_reminders_markdown(chat_id)
            await deps.safe_reply_text(
                reply_target,
                "\n".join(
                    [
                        "Напоминание поставлено.",
                        f"Когда: {deps.format_msk_dt(reminder['remind_at'])}",
                        f"Текст: {reminder['text']}",
                    ]
                ),
            )
        elif parsed["kind"] == "recurring_reminders":
            recurring = parsed["recurring_reminders"]
            reminder_texts = recurring.get("texts") or []
            for index, remind_at in enumerate(recurring["occurrences"]):
                reminder_text = reminder_texts[index] if index < len(reminder_texts) else recurring["text"]
                reminder_id = deps.store.add_reminder(
                    chat_id=chat_id,
                    text=reminder_text,
                    remind_at=remind_at,
                )
                await deps.schedule_reminder(
                    app,
                    reminder_id,
                    chat_id,
                    reminder_text,
                    remind_at,
                )
            deps.export_reminders_markdown(chat_id)
            await deps.safe_reply_text(
                reply_target,
                "\n".join(
                    [
                        "Повторяющиеся напоминания поставлены.",
                        f"Количество: {recurring['count']}",
                        f"Первое: {deps.format_msk_dt(recurring['occurrences'][0])}",
                        f"Последнее: {deps.format_msk_dt(recurring['occurrences'][-1])}",
                    ]
                ),
            )
        elif parsed["kind"] == "recurring_calendar_events":
            recurring = parsed["recurring_calendar_events"]
            for occurrence in recurring["occurrences"]:
                await deps.create_calendar_event_from_fields(
                    title=recurring["title"],
                    start=occurrence["start"],
                    end=occurrence["end"],
                    description=recurring.get("description", ""),
                    reminder_minutes=recurring.get("reminder_minutes"),
                    user_id=user_id,
                )
            await deps.safe_reply_text(
                reply_target,
                "\n".join(
                    [
                        "Повторяющиеся события созданы.",
                        f"Количество: {recurring['count']}",
                        f"Первое: {deps.format_msk_dt(recurring['occurrences'][0]['start'])}",
                        f"Последнее: {deps.format_msk_dt(recurring['occurrences'][-1]['start'])}",
                        f"Напоминание: за {recurring['reminder_minutes']} мин.",
                    ]
                ),
            )
        elif parsed["kind"] == "delete_calendar_event":
            if parsed["delete_event"].get("delete_all"):
                events = await deps.find_calendar_events_limited(parsed, limit=100, user_id=user_id)
                if not events:
                    await deps.safe_reply_text(reply_target, "Не нашел подходящих событий в календаре.")
                else:
                    for event in events:
                        await deps.delete_calendar_event_by_id(event["id"], user_id=user_id)
                    await deps.safe_reply_text(reply_target, f"Удалено событий: {len(events)}")
                return

            events = await deps.find_calendar_events(parsed, user_id=user_id)
            if not events:
                await deps.safe_reply_text(reply_target, "Не нашел подходящих событий в календаре.")
            elif len(events) == 1:
                event = events[0]
                await deps.delete_calendar_event_by_id(event["id"], user_id=user_id)
                await deps.safe_reply_text(reply_target, f"Событие удалено: {deps.calendar_event_label(event)}")
            else:
                await deps.ask_user_to_select_event(
                    reply_target,
                    chat_id,
                    "delete",
                    events,
                    parsed,
                    "Нашел несколько событий. Какое удалить?",
                )
        elif parsed["kind"] == "reschedule_calendar_event":
            delete_shape = {"delete_event": parsed["reschedule_event"]}
            events = await deps.find_calendar_events(delete_shape, user_id=user_id)
            if not events:
                await deps.safe_reply_text(reply_target, "Не нашел подходящих событий в календаре.")
            elif len(events) == 1:
                updated = await deps.reschedule_calendar_event_by_payload(events[0], parsed, user_id=user_id)
                await deps.safe_reply_text(reply_target, f"Событие перенесено: {deps.calendar_event_label(updated)}")
            else:
                await deps.ask_user_to_select_event(
                    reply_target,
                    chat_id,
                    "reschedule",
                    events,
                    parsed,
                    "Нашел несколько событий. Какое перенести?",
                )
        elif parsed["kind"] == "delete_reminders":
            await deps.execute_delete_reminders(parsed, chat_id, reply_target)
        else:
            await deps.safe_reply_text(reply_target, "Неизвестный тип действия.")
    except Exception as exc:
        logger.exception("Action execution failed")
        await deps.safe_reply_text(reply_target, f"Не получилось выполнить действие: {exc}")

