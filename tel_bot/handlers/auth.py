from __future__ import annotations

from typing import Any

from tel_bot.config import ADMIN_CHAT_ID
from tel_bot.handlers.db_access import get_active_access


def _to_int(value: Any) -> Any:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value)
    return value


def normalize_admin_ids() -> list[int]:
    if isinstance(ADMIN_CHAT_ID, (list, set, tuple)):
        return [_to_int(x) for x in ADMIN_CHAT_ID]
    return [_to_int(ADMIN_CHAT_ID)]


def is_admin(user_id: int) -> bool:
    normalized = normalize_admin_ids()
    return user_id in normalized


def is_authorized(user_id: int) -> bool:
    if is_admin(user_id):
        return True
    return get_active_access(user_id) is not None


async def notify_admins(bot, text: str) -> None:
    for admin_id in normalize_admin_ids():
        try:
            await bot.send_message(chat_id=admin_id, text=text)
        except Exception:
            continue

