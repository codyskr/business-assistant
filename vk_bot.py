import asyncio
import json
import logging
import os
import random
from dataclasses import dataclass
from typing import Any

import httpx
from dotenv import load_dotenv

from assistant_core.commands import (
    build_knowledge_reply,
    build_notes_reply,
    build_reminders_reply,
    resolve_help_section,
)
from assistant_core.ids import is_vk_chat_id, vk_identity, vk_peer_id
import bot


load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

VK_API_VERSION = os.getenv("VK_API_VERSION", "5.199")
VK_GROUP_ID = os.getenv("VK_GROUP_ID", "").strip()
VK_GROUP_TOKEN = os.getenv("VK_GROUP_TOKEN", "").strip()
ALLOWED_VK_USER_IDS = {
    int(value.strip())
    for value in os.getenv("ALLOWED_VK_USER_IDS", "").split(",")
    if value.strip().isdigit()
}

def is_allowed_vk_user(user_id: int) -> bool:
    return not ALLOWED_VK_USER_IDS or user_id in ALLOWED_VK_USER_IDS


class VkClient:
    def __init__(self, group_id: str, token: str) -> None:
        self.group_id = group_id
        self.token = token
        self.client = httpx.AsyncClient(timeout=35)

    async def close(self) -> None:
        await self.client.aclose()

    async def api(self, method: str, **params: Any) -> dict[str, Any]:
        payload = {
            "access_token": self.token,
            "v": VK_API_VERSION,
            **params,
        }
        response = await self.client.post(f"https://api.vk.com/method/{method}", data=payload)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            error = data["error"]
            raise RuntimeError(f"VK API {method} failed: {error.get('error_msg', error)}")
        return data["response"]

    async def get_long_poll_server(self) -> dict[str, Any]:
        return await self.api("groups.getLongPollServer", group_id=self.group_id)

    async def poll(self, server: str, key: str, ts: str) -> dict[str, Any]:
        response = await self.client.get(
            server,
            params={
                "act": "a_check",
                "key": key,
                "ts": ts,
                "wait": 25,
                "mode": 2,
                "version": 3,
            },
        )
        response.raise_for_status()
        return response.json()

    async def send_message(self, peer_id: int, text: str) -> None:
        await self.api(
            "messages.send",
            peer_id=peer_id,
            message=text[:4000],
            random_id=random.randint(1, 2_147_483_647),
        )


class VkBotApi:
    def __init__(self, client: VkClient) -> None:
        self.client = client

    async def send_chat_action(self, chat_id: int, action: Any) -> None:
        return None

    async def send_message(self, chat_id: int, text: str, **kwargs: Any) -> None:
        await self.client.send_message(vk_peer_id(chat_id), text)


@dataclass
class VkUser:
    id: int


@dataclass
class VkChat:
    id: int


class VkMessage:
    def __init__(self, client: VkClient, peer_id: int, text: str) -> None:
        self.client = client
        self.peer_id = peer_id
        self.text = text

    async def reply_text(self, text: str, **kwargs: Any) -> None:
        if kwargs.get("reply_markup"):
            text = (
                f"{text}\n\n"
                "VK: РѕС‚РІРµС‚СЊ `РїРѕРґС‚РІРµСЂРґРёС‚СЊ`, С‡С‚РѕР±С‹ РІС‹РїРѕР»РЅРёС‚СЊ РґРµР№СЃС‚РІРёРµ, РёР»Рё `РѕС‚РјРµРЅР°`, С‡С‚РѕР±С‹ РѕС‚РјРµРЅРёС‚СЊ."
            )
        await self.client.send_message(self.peer_id, text)


class VkUpdate:
    def __init__(self, client: VkClient, peer_id: int, from_id: int, text: str) -> None:
        identity = vk_identity(peer_id, from_id)
        self.message = VkMessage(client, peer_id, text)
        self.effective_chat = VkChat(identity.chat_id)
        self.effective_user = VkUser(identity.user_id)


class VkContext:
    def __init__(self, app: "VkApplication", args: list[str] | None = None) -> None:
        self.application = app
        self.bot = app.bot
        self.args = args or []


class VkApplication:
    def __init__(self, client: VkClient) -> None:
        self.bot = VkBotApi(client)


def latest_pending_action(chat_id: int, user_id: int) -> int | None:
    with bot.store.connect() as conn:
        row = conn.execute(
            """
            SELECT id
            FROM pending_actions
            WHERE chat_id = ? AND user_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (chat_id, user_id),
        ).fetchone()
    return int(row["id"]) if row else None


async def confirm_latest(update: VkUpdate, context: VkContext) -> None:
    action_id = latest_pending_action(update.effective_chat.id, update.effective_user.id)
    if action_id is None:
        await update.message.reply_text("РќРµС‚ РґРµР№СЃС‚РІРёСЏ РґР»СЏ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёСЏ.")
        return

    row = bot.store.pop_pending(action_id)
    if not row:
        await update.message.reply_text("Р­С‚Рѕ РґРµР№СЃС‚РІРёРµ СѓР¶Рµ РѕР±СЂР°Р±РѕС‚Р°РЅРѕ РёР»Рё СѓСЃС‚Р°СЂРµР»Рѕ.")
        return

    parsed = json.loads(row["action_json"])
    await bot.execute_action(
        parsed,
        chat_id=int(row["chat_id"]),
        user_id=int(row["user_id"]) if row["user_id"] is not None else None,
        app=context.application,
        reply_target=update.message,
    )


async def cancel_latest(update: VkUpdate) -> None:
    action_id = latest_pending_action(update.effective_chat.id, update.effective_user.id)
    if action_id is None:
        await update.message.reply_text("РќРµС‚ РґРµР№СЃС‚РІРёСЏ РґР»СЏ РѕС‚РјРµРЅС‹.")
        return
    bot.store.pop_pending(action_id)
    await update.message.reply_text("РћС‚РјРµРЅРµРЅРѕ.")


async def schedule_vk_pending_reminders(app: VkApplication) -> None:
    for row in bot.store.list_pending_reminders():
        chat_id = int(row["chat_id"])
        if not is_vk_chat_id(chat_id):
            continue
        remind_at = bot.parse_dt(row["remind_at"])
        if remind_at <= bot.datetime.now(bot.ZoneInfo(bot.TIMEZONE)):
            bot.store.mark_reminder_sent(row["id"])
            continue
        await bot.schedule_reminder(
            app,
            int(row["id"]),
            chat_id,
            str(row["text"]),
            str(row["remind_at"]),
        )


async def handle_vk_text(client: VkClient, app: VkApplication, peer_id: int, from_id: int, text: str) -> None:
    if not text.strip():
        return
    if not is_allowed_vk_user(from_id):
        await client.send_message(peer_id, "Р”РѕСЃС‚СѓРї Рє СЌС‚РѕРјСѓ Р±РѕС‚Сѓ РѕРіСЂР°РЅРёС‡РµРЅ.")
        logger.warning("Blocked VK message from user_id=%s", from_id)
        return

    normalized = text.strip().lower()
    update = VkUpdate(client, peer_id, from_id, text.strip())
    context = VkContext(app)

    if normalized in {"РїРѕРґС‚РІРµСЂРґРёС‚СЊ", "РґР°", "РѕРє", "ok", "+"}:
        await confirm_latest(update, context)
        return
    if normalized in {"РѕС‚РјРµРЅР°", "РѕС‚РјРµРЅРё", "cancel", "-"}:
        await cancel_latest(update)
        return
    if normalized.startswith("/whoami"):
        await update.message.reply_text(
            "\n".join(
                [
                    f"Р’Р°С€ VK user id: {from_id}",
                    f"VK peer id: {peer_id}",
                    f"Р’РЅСѓС‚СЂРµРЅРЅРёР№ chat id: {update.effective_chat.id}",
                ]
            )
        )
        return
    if normalized.startswith("/help"):
        await update.message.reply_text(
            bot.capabilities_text(resolve_help_section(text.split()[1:]))
        )
        return
    if normalized.startswith("/reminders"):
        reply = build_reminders_reply(
            chat_id=update.effective_chat.id,
            args=text.split()[1:],
            now=bot.datetime.now(bot.ZoneInfo(bot.TIMEZONE)),
            reminder_range_from_text=bot.reminder_range_from_text,
            day_bounds=bot.day_bounds,
            export_reminders_markdown=bot.export_reminders_markdown,
            format_reminders_for_range=bot.format_reminders_for_range,
        )
        await update.message.reply_text(reply)
        return
    if normalized.startswith("/notes"):
        reply = await build_notes_reply(
            chat_id=update.effective_chat.id,
            user_id=update.effective_user.id,
            args=text.split()[1:],
            search_notes_contextual=bot.search_notes_contextual,
            iter_notes=bot.iter_notes,
            format_note_results=bot.format_note_results,
            format_msk_dt=bot.format_msk_dt,
        )
        await update.message.reply_text(reply)
        return
    if normalized.startswith("/kb") or normalized.startswith("/knowledge"):
        reply = await build_knowledge_reply(
            chat_id=update.effective_chat.id,
            user_id=update.effective_user.id,
            args=text.split()[1:],
            empty_message=(
                "Р‘Р°Р·Р° Р·РЅР°РЅРёР№ РїРѕРєР° РїСѓСЃС‚Р°СЏ. Р”РѕР±Р°РІР»РµРЅРёРµ С„Р°Р№Р»РѕРІ С‡РµСЂРµР· VK Р±СѓРґРµС‚ РѕС‚РґРµР»СЊРЅС‹Рј СЌС‚Р°РїРѕРј; "
                "СЃРµР№С‡Р°СЃ С„Р°Р№Р»С‹ РґРѕР±Р°РІР»СЏСЋС‚СЃСЏ С‡РµСЂРµР· Telegram."
            ),
            search_knowledge_contextual=bot.search_knowledge_contextual,
            iter_knowledge_chunks=bot.iter_knowledge_chunks,
            format_knowledge_results=bot.format_knowledge_results,
            format_msk_dt=bot.format_msk_dt,
        )
        await update.message.reply_text(reply)
        return

    await bot.handle_text(text, update, context, source="vk_text")


async def run() -> None:
    if not VK_GROUP_ID:
        raise RuntimeError("Set VK_GROUP_ID in .env")
    if not VK_GROUP_TOKEN:
        raise RuntimeError("Set VK_GROUP_TOKEN in .env")

    client = VkClient(VK_GROUP_ID, VK_GROUP_TOKEN)
    app = VkApplication(client)
    try:
        await schedule_vk_pending_reminders(app)
        if not bot.scheduler.running:
            bot.scheduler.start()

        server_data = await client.get_long_poll_server()
        server = server_data["server"]
        key = server_data["key"]
        ts = server_data["ts"]
        logger.info("VK local organizer bot started")

        while True:
            try:
                data = await client.poll(server, key, ts)
                if data.get("failed"):
                    server_data = await client.get_long_poll_server()
                    server = server_data["server"]
                    key = server_data["key"]
                    ts = server_data["ts"]
                    continue
                ts = data["ts"]
                for update in data.get("updates", []):
                    if update.get("type") != "message_new":
                        continue
                    message = update.get("object", {}).get("message", {})
                    peer_id = int(message.get("peer_id") or 0)
                    from_id = int(message.get("from_id") or 0)
                    text = str(message.get("text") or "")
                    await handle_vk_text(client, app, peer_id, from_id, text)
            except Exception:
                logger.exception("VK polling cycle failed")
                await asyncio.sleep(3)
    finally:
        await client.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
