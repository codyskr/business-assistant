from dataclasses import dataclass


# Internal id ranges keep data from different messengers isolated in the shared
# storage until a proper users/workspaces table is introduced.
TELEGRAM_CHAT_OFFSET = 0
TELEGRAM_USER_OFFSET = 0
VK_CHAT_OFFSET = 10_000_000_000_000
VK_USER_OFFSET = 20_000_000_000_000
WEB_CHAT_OFFSET = 30_000_000_000_000
WEB_USER_OFFSET = 40_000_000_000_000
MAX_CHAT_OFFSET = 50_000_000_000_000
MAX_USER_OFFSET = 60_000_000_000_000


@dataclass(frozen=True)
class ChannelIdentity:
    channel: str
    external_chat_id: int
    external_user_id: int
    chat_id: int
    user_id: int


def telegram_identity(chat_id: int, user_id: int) -> ChannelIdentity:
    return ChannelIdentity(
        channel="telegram",
        external_chat_id=chat_id,
        external_user_id=user_id,
        chat_id=TELEGRAM_CHAT_OFFSET + chat_id,
        user_id=TELEGRAM_USER_OFFSET + user_id,
    )


def vk_identity(peer_id: int, user_id: int) -> ChannelIdentity:
    return ChannelIdentity(
        channel="vk",
        external_chat_id=peer_id,
        external_user_id=user_id,
        chat_id=VK_CHAT_OFFSET + peer_id,
        user_id=VK_USER_OFFSET + user_id,
    )


def vk_peer_id(internal_chat_id: int) -> int:
    return internal_chat_id - VK_CHAT_OFFSET


def is_vk_chat_id(internal_chat_id: int) -> bool:
    return VK_CHAT_OFFSET <= internal_chat_id < VK_USER_OFFSET

