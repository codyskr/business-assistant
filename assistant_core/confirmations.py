from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PendingAction:
    id: int
    chat_id: int
    user_id: int | None
    action: dict[str, Any]


def create_pending_action(
    store: Any,
    *,
    chat_id: int,
    user_id: int,
    action: dict[str, Any],
) -> int:
    return int(store.add_pending(chat_id=chat_id, user_id=user_id, action=action))


def latest_pending_action_id(store: Any, *, chat_id: int, user_id: int) -> int | None:
    return store.latest_pending_action_id(chat_id, user_id)


def pop_pending_action(store: Any, action_id: int) -> PendingAction | None:
    row = store.pop_pending(action_id)
    if not row:
        return None
    return PendingAction(
        id=int(row["id"]),
        chat_id=int(row["chat_id"]),
        user_id=int(row["user_id"]) if row["user_id"] is not None else None,
        action=json.loads(row["action_json"]),
    )

