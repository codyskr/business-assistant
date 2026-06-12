from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from assistant_core.confirmations import create_pending_action


logger = logging.getLogger(__name__)


ACTION_KINDS = {
    "calendar_event",
    "reminder",
    "recurring_reminders",
    "recurring_calendar_events",
    "delete_calendar_event",
    "delete_reminders",
    "reschedule_calendar_event",
}


@dataclass(frozen=True)
class AssistantMessageContext:
    chat_id: int
    user_id: int
    app: Any
    reply_target: Any


@dataclass(frozen=True)
class AssistantCoreDeps:
    store: Any
    auto_confirm_actions: bool
    ollama_request_error: type[BaseException] | tuple[type[BaseException], ...]
    safe_reply_text: Callable[..., Awaitable[bool]]
    safe_send_typing: Callable[[Any, int], Awaitable[None]]
    capabilities_text: Callable[[], str]
    capabilities_markup: Callable[[], Any]
    confirmation_markup: Callable[[int], Any]
    is_capabilities_question: Callable[[str], bool]
    maybe_handle_notes: Callable[..., Awaitable[bool]]
    maybe_handle_knowledge_query: Callable[..., Awaitable[bool]]
    reminder_range_from_text: Callable[[str], tuple[str, datetime, datetime] | None]
    export_reminders_markdown: Callable[[int], Any]
    format_reminders_for_range: Callable[[int, str, datetime, datetime], str]
    infer_calendar_list_range: Callable[[str], tuple[str, datetime, datetime] | None]
    list_calendar_events: Callable[..., Awaitable[list[dict[str, Any]]]]
    format_calendar_events: Callable[[list[dict[str, Any]], str], str]
    infer_delete_reminders: Callable[[str], dict[str, Any] | None]
    infer_delete_all_calendar_events: Callable[[str], dict[str, Any] | None]
    infer_recurring_calendar_events: Callable[[str], dict[str, Any] | None]
    infer_hourly_countdown_reminders: Callable[[str], dict[str, Any] | None]
    infer_general_recurring_reminders: Callable[[str], dict[str, Any] | None]
    infer_recurring_task_reminders: Callable[[str], dict[str, Any] | None]
    infer_direct_reminder: Callable[[str], dict[str, Any] | None]
    infer_task_reminder: Callable[[str], dict[str, Any] | None]
    ask_ollama_for_intent: Callable[[str, int], Awaitable[Any]]
    format_action: Callable[[dict[str, Any]], str]
    execute_action: Callable[..., Awaitable[None]]


class AssistantCore:
    def __init__(self, deps: AssistantCoreDeps) -> None:
        self.deps = deps

    async def handle_text(
        self,
        text: str,
        context: AssistantMessageContext,
        *,
        source: str = "text",
        stt_provider: str | None = None,
        debug_id: int | None = None,
    ) -> None:
        deps = self.deps
        if debug_id is None:
            debug_id = deps.store.add_debug_log(
                chat_id=context.chat_id,
                user_id=context.user_id,
                source=source,
                stt_provider=stt_provider,
                input_text=text,
            )

        deps.store.add_memory_message(
            chat_id=context.chat_id,
            user_id=context.user_id,
            role="user",
            text=text,
        )
        await deps.safe_send_typing(context, context.chat_id)

        if deps.is_capabilities_question(text):
            reply = deps.capabilities_text()
            deps.store.update_debug_log(debug_id, intent_kind="capabilities", result="replied")
            await deps.safe_reply_text(
                context.reply_target,
                reply,
                reply_markup=deps.capabilities_markup(),
            )
            deps.store.add_memory_message(
                chat_id=context.chat_id,
                user_id=None,
                role="assistant",
                text=reply,
            )
            return

        if await deps.maybe_handle_notes(
            text,
            chat_id=context.chat_id,
            user_id=context.user_id,
            reply_target=context.reply_target,
            debug_id=debug_id,
        ):
            return

        if await deps.maybe_handle_knowledge_query(
            text,
            chat_id=context.chat_id,
            user_id=context.user_id,
            reply_target=context.reply_target,
            debug_id=debug_id,
        ):
            return

        reminder_range = deps.reminder_range_from_text(text)
        if reminder_range:
            title, start, end = reminder_range
            deps.export_reminders_markdown(context.chat_id)
            reply = deps.format_reminders_for_range(context.chat_id, title, start, end)
            deps.store.update_debug_log(debug_id, intent_kind="reminder_list", result="replied")
            await deps.safe_reply_text(context.reply_target, reply)
            deps.store.add_memory_message(
                chat_id=context.chat_id,
                user_id=None,
                role="assistant",
                text=reply,
            )
            return

        calendar_range = deps.infer_calendar_list_range(text)
        if calendar_range:
            title, start, end = calendar_range
            try:
                events = await deps.list_calendar_events(start, end, user_id=context.user_id)
                reply = deps.format_calendar_events(events, title)
                deps.store.update_debug_log(debug_id, intent_kind="calendar_list", result="replied")
            except Exception as exc:
                logger.exception("Calendar listing failed")
                reply = f"Не получилось прочитать календарь: {exc}"
                deps.store.update_debug_log(
                    debug_id,
                    intent_kind="calendar_list",
                    result="error",
                    error=str(exc),
                )

            await deps.safe_reply_text(context.reply_target, reply)
            deps.store.add_memory_message(
                chat_id=context.chat_id,
                user_id=None,
                role="assistant",
                text=reply,
            )
            return

        task_reminder = (
            deps.infer_delete_reminders(text)
            or deps.infer_delete_all_calendar_events(text)
            or deps.infer_recurring_calendar_events(text)
            or deps.infer_hourly_countdown_reminders(text)
            or deps.infer_general_recurring_reminders(text)
            or deps.infer_recurring_task_reminders(text)
            or deps.infer_direct_reminder(text)
            or deps.infer_task_reminder(text)
        )
        if task_reminder:
            await self._handle_action(
                task_reminder,
                kind="reminder",
                debug_id=debug_id,
                context=context,
            )
            return

        try:
            intent = await deps.ask_ollama_for_intent(text, context.chat_id)
        except deps.ollama_request_error:
            deps.store.update_debug_log(debug_id, result="error", error="ollama_request_error")
            await deps.safe_reply_text(
                context.reply_target,
                "Не могу подключиться к Ollama. Проверьте, что ollama serve запущен.",
            )
            return
        except Exception as exc:
            logger.exception("Intent parsing failed")
            deps.store.update_debug_log(debug_id, result="error", error=str(exc))
            await deps.safe_reply_text(
                context.reply_target,
                "Не смог разобрать запрос. Попробуйте сказать проще и с датой/временем.",
            )
            return

        if intent.kind in ACTION_KINDS:
            await self._handle_action(
                intent.data,
                kind=intent.kind,
                debug_id=debug_id,
                context=context,
                add_history=True,
            )
            return

        deps.store.update_debug_log(
            debug_id,
            intent_kind=intent.kind,
            intent_payload=intent.data,
            result="chat_reply",
        )
        await deps.safe_reply_text(context.reply_target, intent.reply)
        deps.store.add_memory_message(
            chat_id=context.chat_id,
            user_id=None,
            role="assistant",
            text=intent.reply,
        )

    async def _handle_action(
        self,
        action: dict[str, Any],
        *,
        kind: str,
        debug_id: int | None,
        context: AssistantMessageContext,
        add_history: bool = False,
    ) -> None:
        deps = self.deps
        action_summary = deps.format_action(action)
        deps.store.update_debug_log(
            debug_id,
            intent_kind=kind,
            intent_payload=action,
            result="auto_confirm_execute" if deps.auto_confirm_actions else "pending_confirmation",
        )
        if add_history:
            deps.store.add_action_history(context.chat_id, kind, action_summary, action)

        if deps.auto_confirm_actions:
            await deps.execute_action(
                action,
                chat_id=context.chat_id,
                user_id=context.user_id,
                app=context.app,
                reply_target=context.reply_target,
            )
            return

        action_id = create_pending_action(
            deps.store,
            chat_id=context.chat_id,
            user_id=context.user_id,
            action=action,
        )
        await deps.safe_reply_text(
            context.reply_target,
            action_summary,
            reply_markup=deps.confirmation_markup(action_id),
        )
        deps.store.add_memory_message(
            chat_id=context.chat_id,
            user_id=None,
            role="assistant",
            text=action_summary,
        )

