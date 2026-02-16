from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Dict, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


RUNS_KEY = "active_runs"  # bot_data registry: { chat_id: { run_id: run_data } }


def runs(context: ContextTypes.DEFAULT_TYPE) -> Dict[int, Dict[str, Dict[str, Any]]]:
    registry = context.application.bot_data.get(RUNS_KEY)
    if registry is None:
        registry = {}
        context.application.bot_data[RUNS_KEY] = registry
    return registry


def start_run_for_chat(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    target,
    args: tuple,
    *,
    student_number: str | None = None,
    course_list: list[dict] | None = None,
    allow_multiple: bool = False,
    run_id: str | None = None,
) -> Optional[str]:
    """
    Start a background run for this chat.
    - If allow_multiple=False, only one active run is allowed per chat.
    Returns run_id if started, otherwise None.
    """
    registry = runs(context)
    chat_runs = registry.setdefault(chat_id, {})

    if not allow_multiple:
        for data in chat_runs.values():
            try:
                if data["thread"].is_alive():
                    return None
            except Exception:
                continue

    run_id = run_id or uuid.uuid4().hex[:10]
    cancel_event = threading.Event()

    run_data: dict[str, Any] = {
        "id": run_id,
        "thread": None,
        "cancel_event": cancel_event,
        "status": "running",
        "student_number": student_number,
        "course_list": course_list,
        "started_at": time.time(),
        "finished_at": None,
        "error": None,
    }

    def _runner() -> None:
        try:
            target(*args, cancel_event)
            run_data["status"] = "canceled" if cancel_event.is_set() else "completed"
        except Exception as e:
            run_data["status"] = "error"
            run_data["error"] = str(e)
        finally:
            run_data["finished_at"] = time.time()

    thread = threading.Thread(target=_runner, daemon=True)
    run_data["thread"] = thread
    chat_runs[run_id] = run_data
    thread.start()
    return run_id


def cancel_run_for_chat(context: ContextTypes.DEFAULT_TYPE, chat_id: int, run_id: str | None = None) -> bool:
    """
    Signal cancel for a run.
    - If run_id is None, cancels the most recent running run in this chat.
    Returns True if a run existed and was signaled.
    """
    registry = runs(context)
    chat_runs = registry.get(chat_id) or {}

    if run_id:
        data = chat_runs.get(run_id)
        if not data:
            return False
        data["cancel_event"].set()
        return True

    for data in sorted(chat_runs.values(), key=lambda d: d.get("started_at") or 0, reverse=True):
        try:
            if data["thread"].is_alive() and data.get("status") == "running":
                data["cancel_event"].set()
                return True
        except Exception:
            continue
    return False


def prune_runs_for_chat(context: ContextTypes.DEFAULT_TYPE, chat_id: int, *, keep_last: int = 25) -> None:
    """Keep a bounded run history per chat."""
    registry = runs(context)
    chat_runs = registry.get(chat_id)
    if not chat_runs:
        return

    now = time.time()
    # Drop very old finished runs (6h)
    for rid, data in list(chat_runs.items()):
        finished_at = data.get("finished_at")
        try:
            alive = data["thread"].is_alive()
        except Exception:
            alive = False
        if finished_at and not alive and (now - float(finished_at) > 6 * 60 * 60):
            chat_runs.pop(rid, None)

    # Enforce keep_last for finished runs (never drop running)
    running: list[dict[str, Any]] = []
    finished: list[dict[str, Any]] = []
    for data in chat_runs.values():
        try:
            alive = data["thread"].is_alive()
        except Exception:
            alive = False
        if alive and data.get("status") == "running":
            running.append(data)
        else:
            finished.append(data)

    finished.sort(key=lambda d: d.get("started_at") or 0, reverse=True)
    keep_finished = max(0, keep_last - len(running))
    for data in finished[keep_finished:]:
        chat_runs.pop(data["id"], None)


def get_runs_for_chat(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> list[dict[str, Any]]:
    registry = runs(context)
    chat_runs = registry.get(chat_id) or {}
    return sorted(chat_runs.values(), key=lambda d: d.get("started_at") or 0, reverse=True)


def get_run(context: ContextTypes.DEFAULT_TYPE, chat_id: int, run_id: str) -> Optional[dict[str, Any]]:
    registry = runs(context)
    chat_runs = registry.get(chat_id) or {}
    return chat_runs.get(run_id)


def cancel_keyboard(run_id: str | None = None) -> InlineKeyboardMarkup:
    data = f"cancel_run:{run_id}" if run_id else "cancel_run"
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ توقف عملیات", callback_data=data)]]
    )
