from __future__ import annotations

import asyncio

from telegram.ext import Application

from tel_bot.message_queue import message_queue


async def _mq_worker(application: Application, worker_id: int = 0) -> None:
    """
    Long-lived async task: blocks on queue.get() off-thread and sends messages
    immediately as they arrive.
    """
    bot = application.bot
    while True:
        chat_id, message = await asyncio.to_thread(message_queue.get)
        recipients = chat_id if isinstance(chat_id, (list, tuple, set)) else [chat_id]
        try:
            for recipient_id in recipients:
                try:
                    await bot.send_message(chat_id=recipient_id, text=message)
                except Exception:
                    continue
        finally:
            try:
                message_queue.task_done()
            except Exception:
                pass


async def start_message_queue_workers(application: Application, workers: int = 3) -> None:
    """
    Start N background workers that drain the queue immediately.
    IMPORTANT: Call from Application.post_init (loop is running).
    """
    for i in range(workers):
        application.create_task(_mq_worker(application, worker_id=i), name=f"mq_worker_{i}")
