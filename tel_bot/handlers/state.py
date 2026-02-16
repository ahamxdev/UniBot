from __future__ import annotations

from telegram.ext import ContextTypes


PERSISTENT_USER_KEYS = {"agreed_to_terms"}


def clear_transient_state(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    keep_keys: set[str] = PERSISTENT_USER_KEYS,
) -> None:
    keep: dict = {k: context.user_data.get(k) for k in keep_keys if k in context.user_data}
    context.user_data.clear()
    context.user_data.update(keep)

