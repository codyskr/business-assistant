from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from datetime import datetime
from typing import Any


HELP_ALIASES = {
    "calendar": "calendar",
    "календарь": "calendar",
    "reminders": "reminders",
    "напоминания": "reminders",
    "voice": "voice",
    "голос": "voice",
    "memory": "memory",
    "память": "memory",
    "knowledge": "knowledge",
    "kb": "knowledge",
    "база": "knowledge",
    "база_знаний": "knowledge",
    "notes": "notes",
    "заметки": "notes",
    "заметка": "notes",
}


def resolve_help_section(args: list[str] | tuple[str, ...]) -> str:
    section = args[0].lower() if args else "main"
    return HELP_ALIASES.get(section, "main")


def build_reminders_reply(
    *,
    chat_id: int,
    args: list[str],
    now: datetime,
    reminder_range_from_text: Callable[[str], tuple[str, datetime, datetime] | None],
    day_bounds: Callable[[datetime], tuple[datetime, datetime]],
    export_reminders_markdown: Callable[[int], Any],
    format_reminders_for_range: Callable[[int, str, datetime, datetime], str],
) -> str:
    text = " ".join(args) if args else "сегодня"
    parsed = reminder_range_from_text(f"список напоминаний {text}")
    if not parsed:
        start, end = day_bounds(now)
        parsed = ("Дела и напоминания на сегодня:", start, end)

    title, start, end = parsed
    export_reminders_markdown(chat_id)
    return format_reminders_for_range(chat_id, title, start, end)


async def build_notes_reply(
    *,
    chat_id: int,
    user_id: int | None,
    args: list[str],
    search_notes_contextual: Callable[..., Awaitable[list[dict[str, Any]]]],
    iter_notes: Callable[..., Iterable[dict[str, Any]]],
    format_note_results: Callable[[str, list[dict[str, Any]]], str],
    format_msk_dt: Callable[[str], str],
) -> str:
    query = " ".join(args).strip()
    if query:
        notes = await search_notes_contextual(chat_id, query, user_id=user_id)
        return format_note_results(query, notes)

    notes = list(reversed(list(iter_notes(chat_id, user_id=user_id))))[:10]
    if not notes:
        return "Заметок пока нет. Скажи: сделай заметку <текст>."

    lines = ["Последние заметки:"]
    for index, note in enumerate(notes, start=1):
        lines.append(f"{index}. {format_msk_dt(note['created_at'])} — {note['text']}")
    return "\n".join(lines)


async def build_knowledge_reply(
    *,
    chat_id: int,
    user_id: int | None,
    args: list[str],
    empty_message: str,
    search_knowledge_contextual: Callable[..., Awaitable[list[dict[str, Any]]]],
    iter_knowledge_chunks: Callable[..., Iterable[dict[str, Any]]],
    format_knowledge_results: Callable[[str, list[dict[str, Any]]], str],
    format_msk_dt: Callable[[str], str],
) -> str:
    query = " ".join(args).strip()
    if query:
        chunks = await search_knowledge_contextual(chat_id, query, user_id=user_id)
        return format_knowledge_results(query, chunks)

    documents: dict[str, dict[str, Any]] = {}
    for chunk in iter_knowledge_chunks(chat_id, user_id=user_id):
        document_id = str(chunk.get("document_id"))
        if document_id not in documents:
            documents[document_id] = {
                "filename": chunk.get("filename", "file"),
                "created_at": chunk.get("created_at"),
                "chunk_count": chunk.get("chunk_count", 0),
            }

    if not documents:
        return empty_message

    lines = ["Файлы в базе знаний:"]
    for index, doc in enumerate(
        sorted(documents.values(), key=lambda item: item.get("created_at", ""), reverse=True),
        start=1,
    ):
        lines.append(
            f"{index}. {doc['filename']} — {doc['chunk_count']} фрагм., {format_msk_dt(doc['created_at'])}"
        )
    return "\n".join(lines[:21])

