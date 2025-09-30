# tel_bot/handlers.py
"""
Telegram update handlers + queue workers + cooperative cancel support.

Highlights
----------
- Event-driven queue workers: messages pushed to `message_queue` are delivered
  immediately (no interval JobQueue needed).
- Cooperative cancel for long-running registration: a per-chat cancel Event is
  stored in bot_data; the background thread checks it and exits cleanly.
- Prevents overlapping runs per chat: one active run per user.

Public API
----------
- start(update, context)
- handle_message(update, context)
- button_handler(update, context)
- start_message_queue_workers(application, workers=3)
"""

from __future__ import annotations

import asyncio
import threading
from typing import Optional, Tuple, Dict, Any, Iterable

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, Application

from tel_bot.keyboard import (
    main_menu_keyboard,
    admin_menu_keyboard,
    back_home_keyboard,
    post_selection_keyboard,
    payment_options_keyboard,
)
from tel_bot.config import ADMIN_CHAT_ID, AUTHORIZED_USERS
from db.models import StudentStatus
from db.db import SessionLocal
from main.main import main  # main(stno, term_code, cookie, course_list, chat_id, cancel_event)
from tel_bot.message_queue import message_queue


# ---------------------------
# Config
# ---------------------------
TERM_CODE = 14041
RUNS_KEY = "active_runs"  # bot_data registry: { chat_id: {"thread": Thread, "cancel_event": Event} }


# ---------------------------
# Helpers: roles, menus, admin send
# ---------------------------
def _is_admin(user_id: int) -> bool:
    """Return True if user_id is in ADMIN_CHAT_ID (supports single or iterable)."""
    if isinstance(ADMIN_CHAT_ID, (list, set, tuple)):
        return user_id in ADMIN_CHAT_ID
    return user_id == ADMIN_CHAT_ID


def _is_authorized(user_id: int) -> bool:
    """
    Return True if user_id is in AUTHORIZED_USERS (supports single or iterable).
    """
    if isinstance(AUTHORIZED_USERS, (list, set, tuple)):
        return user_id in AUTHORIZED_USERS
    return user_id == AUTHORIZED_USERS


def get_main_menu_for_user(user_id: int):
    return admin_menu_keyboard() if _is_admin(user_id) else main_menu_keyboard()


def get_student_number_by_telegram_id(user_id: int) -> Optional[str]:
    """Look up the student's number (stno) by Telegram user_id."""
    session = SessionLocal()
    try:
        student = (
            session.query(StudentStatus)
            .filter_by(telegram_user_id=str(user_id))
            .first()
        )
        if student and student.student_number:
            return student.student_number
        return None
    finally:
        session.close()


def _normalize_admin_ids() -> list[int]:
    """
    Normalize ADMIN_CHAT_ID to a list of ints.
    Supports:
      - single int
      - single str of digits (e.g., from env)
      - iterable of ints/strs
    """
    def _to_int(x: Any):
        if isinstance(x, int):
            return x
        if isinstance(x, str) and x.strip().lstrip("-").isdigit():
            return int(x)
        return x  # leave as-is; send may fail (silently ignored)

    if isinstance(ADMIN_CHAT_ID, (list, set, tuple)):
        return [_to_int(x) for x in ADMIN_CHAT_ID]
    return [_to_int(ADMIN_CHAT_ID)]


async def _notify_admins(bot, text: str) -> None:
    """Send `text` to all admin chat ids (robust to single/multiple ids)."""
    for admin_id in _normalize_admin_ids():
        try:
            await bot.send_message(chat_id=admin_id, text=text)
        except Exception:
            # Optionally log in dev
            continue


# ---------------------------
# Queue workers (event-driven)
# ---------------------------
async def _mq_worker(application: Application, worker_id: int = 0) -> None:
    """
    Long-lived async task: blocks on queue.get() off-thread and sends messages
    immediately as they arrive.
    """
    bot = application.bot
    while True:
        chat_id, message = await asyncio.to_thread(message_queue.get)
        try:
            await bot.send_message(chat_id=chat_id, text=message)
        except Exception:
            pass
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


# ---------------------------
# Run registry & cancel helpers
# ---------------------------
def _runs(context: ContextTypes.DEFAULT_TYPE) -> Dict[int, Dict[str, Any]]:
    d = context.application.bot_data.get(RUNS_KEY)
    if d is None:
        d = {}
        context.application.bot_data[RUNS_KEY] = d
    return d


def _start_run_for_chat(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    target,
    args_tuple: tuple,
) -> bool:
    """
    Start a background thread for this chat if none is active.
    Returns True if started, False if already running.
    """
    runs = _runs(context)
    # Clean stale record
    if chat_id in runs and not runs[chat_id]["thread"].is_alive():
        runs.pop(chat_id, None)

    if chat_id in runs:
        return False  # already active

    cancel_event = threading.Event()
    t = threading.Thread(target=target, args=(*args_tuple, cancel_event), daemon=True)
    t.start()
    runs[chat_id] = {"thread": t, "cancel_event": cancel_event}
    return True


def _cancel_run_for_chat(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> bool:
    """
    Signal cancel for the active run of this chat (if any).
    Returns True if a run existed and was signaled.
    """
    runs = _runs(context)
    data = runs.get(chat_id)
    if not data:
        return False
    data["cancel_event"].set()
    return True


def _clear_run_if_finished(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    """Remove finished run record from registry (optional hygiene)."""
    runs = _runs(context)
    data = runs.get(chat_id)
    if data and not data["thread"].is_alive():
        runs.pop(chat_id, None)


def _cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ توقف عملیات", callback_data="cancel_run")]]
    )


# ---------------------------
# Handlers
# ---------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _is_authorized(user_id):
        await update.message.reply_text("⚠️ شما اجازه دسترسی به این بات را ندارید.")
        return
    if context.user_data.get("agreed_to_terms"):
        await update.message.reply_text(
            "👋 منوی اصلی:", reply_markup=get_main_menu_for_user(user_id)
        )
        return

    terms_text = (
        "<b>📜 شرایط و ضوابط استفاده از بات:</b>\n\n"
        "🔹 این ربات یک ابزار کمکی غیررسمی برای <b>ساده سازی فرآیند انتخاب واحد</b> در سامانه آموزش دانشگاه است و "
        "هیچ گونه وابستگی به دانشگاه یا سامانه آموزش ندارد.\n\n"
        "🔸 برای استفاده، لازم است کاربر اطلاعاتی مانند <b>کوکی مرورگر، کد دانشجویی و ترم جاری</b> را با آگاهی کامل وارد کند. "
        "این اطلاعات فقط به صورت موقت و صرفاً برای اجرای همان درخواست استفاده می شوند.\n\n"
        "🔹 ربات به <b>رمز عبور</b> یا داده های حساس شما <b>دسترسی ندارد</b> و هیچ یک از اطلاعات وارد شده ذخیره، تحلیل یا منتشر نمی شوند.\n\n"
        "🔸 ربات فقط درخواست هایی را ارسال می کند که شما <b>مجاز به انجام آن ها</b> در سامانه هستید. استفاده نادرست از اطلاعات دیگران "
        "یا ارسال درخواست های سنگین، می تواند منجر به <b>محدودیت دسترسی</b> توسط سامانه آموزش شود. در این صورت، <b>مسئولیت کامل بر عهده کاربر</b> است.\n\n"
        "⚠️ با استفاده از این ربات، شما تأیید می کنید که این موارد را مطالعه کرده اید و <b>مسئولیت استفاده بر عهده خودتان</b> است."
    )

    terms_keyboard = back_home_keyboard([["✅ مطالعه کرده و موافقت میکنم"]])
    await update.message.reply_text(
        text=terms_text, parse_mode="HTML", reply_markup=terms_keyboard
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # CallbackQuery-only
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if not _is_authorized(user_id):
        await update.message.reply_text("⚠️ شما اجازه دسترسی به این بات را ندارید.")
        return
    chat_id = query.message.chat.id
    data = query.data

    # --- Cancel current run ---
    if data == "cancel_run":
        ok = _cancel_run_for_chat(context, chat_id)
        if ok:
            await context.bot.send_message(chat_id=chat_id, text="⛔️ عملیات متوقف شد. لطفاً چند لحظه صبر کنید.")
        else:
            await context.bot.send_message(chat_id=chat_id, text="ℹ️ عملیات فعالی برای توقف یافت نشد.")
        _clear_run_if_finished(context, chat_id)
        return

    if data.startswith("term_"):
        selected_term = data.replace("term_", "")
        context.user_data["term"] = selected_term
        student_code = context.user_data.get("student_code", "نامشخص")

        confirm_keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ تایید میکنم", callback_data="confirm_student_info"
                    ),
                    InlineKeyboardButton(
                        "🔄 اشتباهه، تغییر میدم", callback_data="edit_student_info"
                    ),
                ]
            ]
        )

        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "📌 اطلاعات وارد شده:\n\n"
                f"کد دانشجویی: <b>{student_code}</b>\n"
                f"ترم: <b>{selected_term}</b>\n\n"
                "آیا تایید می کنی؟"
            ),
            parse_mode="HTML",
            reply_markup=confirm_keyboard,
        )

    elif data == "confirm_student_info":
        student_code = context.user_data.get("student_code")
        telegram_user_id = str(chat_id)

        session = SessionLocal()
        try:
            existing_status = (
                session.query(StudentStatus)
                .filter_by(telegram_user_id=telegram_user_id)
                .first()
            )
            if existing_status:
                existing_status.student_number = student_code
            else:
                new_status = StudentStatus(
                    telegram_user_id=telegram_user_id, student_number=student_code
                )
                session.add(new_status)

            session.commit()

            await context.bot.send_message(
                chat_id=chat_id,
                text="✅ اطلاعات دانشجویی شما با موفقیت ثبت شد.",
                reply_markup=get_main_menu_for_user(user_id),
            )
        except Exception as e:
            await context.bot.send_message(
                chat_id=chat_id, text="❌ خطایی در ذخیره اطلاعات رخ داد."
            )
            print(f"[Student save error]: {e}")
        finally:
            session.close()
            context.user_data.clear()

    elif data == "already_saved_continue":
        await context.bot.send_message(
            chat_id=chat_id,
            text="اطلاعات شما ذخیره شده.\n\n🏠 منوی اصلی:",
            reply_markup=get_main_menu_for_user(user_id),
        )
        context.user_data.clear()

    elif data == "edit_student_info":
        context.user_data.clear()
        context.user_data["awaiting_student_code"] = True
        await context.bot.send_message(
            chat_id=chat_id,
            text="👤 لطفاً کد دانشجویی خود را وارد کن:",
            reply_markup=back_home_keyboard(),
        )

    elif data in ["select_unit", "remove_unit"]:
        course = context.user_data.get("course_code", "نامشخص")
        group = context.user_data.get("group_code", "نامشخص")
        action_text = "انتخاب واحد" if data == "select_unit" else "حذف واحد"
        symbol = "✅" if data == "select_unit" else "❌"

        context.user_data.setdefault("selected_courses", []).append(
            {"course_code": course, "group_code": group, "action": action_text}
        )

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{symbol} {action_text} انجام شد.\nدرس: {course}\nگروه: {group}",
            reply_markup=post_selection_keyboard(),
        )

        context.user_data.pop("course_code", None)
        context.user_data.pop("group_code", None)

    elif data == "back_home":
        await context.bot.send_message(
            chat_id=chat_id,
            text="🏠 منوی اصلی:",
            reply_markup=get_main_menu_for_user(user_id),
        )
        context.user_data.clear()


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    BROADCAST_CONCURRENCY = 8
    user_id = update.effective_user.id
    if not _is_authorized(user_id):
        await update.message.reply_text("⚠️ شما اجازه دسترسی به این بات را ندارید.")
        return
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()

    # Clear stale run record, if any
    _clear_run_if_finished(context, chat_id)

    # --- Feedback flow ---
    if context.user_data.get("feedback_mode"):
        context.user_data["feedback_mode"] = False

        user = update.effective_user
        username = f"@{user.username}" if user.username else f"ID:{user.id}"
        feedback = f"📩 انتقاد جدید از {username}:\n\n\"{text}\""

        await _notify_admins(context.bot, feedback)

        # اینجا رو تغییر دادم: تشکر + منوی اصلی
        await update.message.reply_text(
            "🙏 ممنون که نظرت رو گفتی!\n\n🏠 منوی اصلی:",
            reply_markup=get_main_menu_for_user(user.id),
        )
        return

    # --- Normal flow ---
    if text == "/start":
        await start(update, context)
        return

    if text == "✅ مطالعه کرده و موافقت میکنم":
        context.user_data["agreed_to_terms"] = True
        await update.message.reply_text(
            "ممنون از موافقتت 🙏\n\n📌 حالا یکی از گزینه های زیر را انتخاب کن 👇",
            reply_markup=get_main_menu_for_user(user_id),
        )
        return

    if text == "❌ انصراف":
        # If a run is active, cancel it first
        if _cancel_run_for_chat(context, chat_id):
            await update.message.reply_text("⛔️ عملیات جاری متوقف شد.")
        context.user_data.clear()
        await update.message.reply_text(
            "🏠 منوی اصلی:", reply_markup=get_main_menu_for_user(user_id)
        )
        return

    if text == "👨‍🎓 اطلاعات دانشجویی":
        context.user_data.clear()
        telegram_user_id = str(chat_id)

        session = SessionLocal()
        try:
            student = (
                session.query(StudentStatus)
                .filter_by(telegram_user_id=telegram_user_id)
                .first()
            )
            if student and student.student_number:
                context.user_data["existing_student"] = True
                await update.message.reply_text(
                    "✅ اطلاعات دانشجویی ثبت شده:\n\n"
                    f"👤 کد دانشجویی: <b>{student.student_number}</b>\n"
                    f"کد ترم: <b>{TERM_CODE}</b>",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "✅ تایید و ادامه",
                                    callback_data="already_saved_continue",
                                ),
                                InlineKeyboardButton(
                                    "🔄 تغییر اطلاعات", callback_data="edit_student_info"
                                ),
                            ]
                        ]
                    ),
                )
                return
            else:
                context.user_data["awaiting_student_code"] = True
                await update.message.reply_text("📝 لطفاً اطلاعات دانشجویی خود را وارد کنید")
                await update.message.reply_text(
                    "👤 لطفاً کد دانشجویی خود را وارد کنید:",
                    reply_markup=back_home_keyboard(),
                )
                return
        finally:
            session.close()

    # انتخاب ترم پس از وارد کردن کد دانشجویی
    if context.user_data.get("awaiting_student_code"):
        if not text.isdigit():
            await update.message.reply_text(
                "⚠️ مقدار کد دانشجویی وارد شده معتبر نیست!\n\nلطفا مقدار صحیح را وارد کنید:"
            )
            return

        context.user_data["student_code"] = text
        context.user_data["awaiting_student_code"] = False

        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(str(TERM_CODE), callback_data=f"term_{TERM_CODE}")]]
        )

        await update.message.reply_text("📘 لطفاً کد ترم را انتخاب کن:", reply_markup=keyboard)
        return

    if text == "📚 انتخاب واحد":
        # بررسی وجود اطلاعات دانشجو
        student = get_student_number_by_telegram_id(user_id)
        if not student:
            await update.message.reply_text(
                "❌ شما هنوز اطلاعات خود را ثبت نکرده‌اید.\n\n"
                "لطفاً ابتدا اطلاعات خود را از بخش اطلاعات دانشجویی وارد کنید.",
                reply_markup=back_home_keyboard(),
            )
            return

        context.user_data.clear()
        context.user_data["awaiting_course_code"] = True
        await update.message.reply_text(
            "📘 لطفاً کد درس را وارد کن:", reply_markup=back_home_keyboard()
        )
        return

    if context.user_data.get("awaiting_course_code"):
        if text == "❌ انصراف":
            _cancel_run_for_chat(context, chat_id)
            context.user_data.clear()
            await update.message.reply_text(
                "🏠 منوی اصلی:", reply_markup=get_main_menu_for_user(user_id)
            )
            return

        if not text.isdigit():
            await update.message.reply_text(
                "⚠️ مقدار کد درس وارد شده معتبر نیست!\n\nلطفا مقدار صحیح را وارد کنید."
            )
            return

        context.user_data["course_code"] = text
        context.user_data["awaiting_course_code"] = False
        context.user_data["awaiting_group_code"] = True

        await update.message.reply_text(
            "✍️ لطفاً کد گروه را وارد کن:", reply_markup=back_home_keyboard()
        )
        return

    if context.user_data.get("awaiting_group_code"):
        if text == "❌ انصراف":
            _cancel_run_for_chat(context, chat_id)
            context.user_data.clear()
            await update.message.reply_text(
                "🏠 منوی اصلی:", reply_markup=get_main_menu_for_user(user_id)
            )
            return

        if not text.isdigit():
            await update.message.reply_text(
                "⚠️ مقدار کد گروه وارد شده معتبر نیست!\n\nلطفا مقدار صحیح را وارد کنید."
            )
            return

        context.user_data["group_code"] = text
        context.user_data["awaiting_group_code"] = False

        inline_buttons = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ انتخاب واحد", callback_data="select_unit")],
                [InlineKeyboardButton("❌ حذف واحد", callback_data="remove_unit")],
            ]
        )

        await update.message.reply_text(
            "✅ لطفاً یکی از گزینه های زیر را انتخاب کن:", reply_markup=inline_buttons
        )
        return

    if text == "➕ افزودن درس دیگر":
        context.user_data["awaiting_course_code"] = True
        await update.message.reply_text(
            "📘 لطفاً کد درس جدید را وارد کن:", reply_markup=back_home_keyboard()
        )
        return

    if text == "✅ نهایی کردن عملیات":
        selected_courses = context.user_data.get("selected_courses", [])
        if not selected_courses:
            await update.message.reply_text(
                "⚠️ هنوز درسی ثبت نشده است!",
                reply_markup=get_main_menu_for_user(user_id),
            )
            return

        summary = "📚 لیست نهایی عملیات:\n"
        for i, course in enumerate(selected_courses, 1):
            summary += (
                f"{i}. درس {course['course_code']} - گروه {course['group_code']} "
                f"({course['action']})\n"
            )

        context.user_data["awaiting_cookie"] = True
        await update.message.reply_text(
            summary
            + "\n🧠 حالا لطفاً کوکی موجود در مرورگر خود را جهت انجام عملیات انتخاب و حذف واحد "
              "طبق آموزش انجام شده در بخش راهنمای بات وارد کنید:",
            reply_markup=back_home_keyboard(),
        )
        return

# --- Start broadcast flow (admin reply-keyboard button) ---
    if text == "💬 ارسال پیام همگانی" and user_id in AUTHORIZED_USERS:
        # enter broadcast mode: next text message from this admin is the broadcast body
        context.user_data["broadcast_mode"] = True
        await update.message.reply_text(
            "✍️ لطفاً متن پیام همگانی را وارد کنید:\n(ارسال به همه‌ی کاربران مجاز)",
            reply_markup=back_home_keyboard(),
        )
        return

# inside handle_message, where you handle broadcast_mode:
    if context.user_data.get("broadcast_mode"):
        # only allow authorized admins to actually broadcast
        if user_id not in AUTHORIZED_USERS:
            context.user_data.pop("broadcast_mode", None)
            await update.message.reply_text("❌ شما اجازهٔ ارسال پیام همگانی را ندارید.", reply_markup=get_main_menu_for_user(user_id))
            return

        # consume the flag
        context.user_data.pop("broadcast_mode", None)

        # Detect message type and extract payload
        msg = update.message

        kind = "text"
        payload = {"text": (msg.text or "").strip()}

        # Photo (pick highest resolution)
        if msg.photo:
            kind = "photo"
            file_id = msg.photo[-1].file_id
            payload = {"file_id": file_id, "caption": (msg.caption or "").strip()}

        # Video
        elif msg.video:
            kind = "video"
            payload = {"file_id": msg.video.file_id, "caption": (msg.caption or "").strip()}

        # Document (pdf, etc.)
        elif msg.document:
            kind = "document"
            payload = {"file_id": msg.document.file_id, "filename": msg.document.file_name, "caption": (msg.caption or "").strip()}

        # Voice / audio etc. can be added similarly

        # Async sender using semaphore to limit concurrent API calls
        sem = asyncio.Semaphore(BROADCAST_CONCURRENCY)

        async def _send_one(recipient_id: int) -> tuple[int, bool, str]:
            """
            Send payload to recipient_id.
            Returns tuple(recipient_id, success_bool, error_message_or_empty).
            """
            try:
                async with sem:
                    if kind == "text":
                        await context.bot.send_message(chat_id=recipient_id, text=payload["text"])
                    elif kind == "photo":
                        await context.bot.send_photo(chat_id=recipient_id, photo=payload["file_id"], caption=payload.get("caption") or None)
                    elif kind == "video":
                        await context.bot.send_video(chat_id=recipient_id, video=payload["file_id"], caption=payload.get("caption") or None)
                    elif kind == "document":
                        await context.bot.send_document(chat_id=recipient_id, document=payload["file_id"], caption=payload.get("caption") or None)
                    else:
                        # fallback to text
                        await context.bot.send_message(chat_id=recipient_id, text=payload.get("text",""))
                return (recipient_id, True, "")
            except Exception as e:
                # return error to report back to admin; do not raise
                return (recipient_id, False, str(e))

        # Launch tasks for all recipients and wait
        recipients = list(AUTHORIZED_USERS)  # or your target list of users
        tasks = [_send_one(uid) for uid in recipients]
        results = await asyncio.gather(*tasks)

        # Process results
        failures = [(rid, err) for (rid, ok, err) in results if not ok]
        success_count = sum(1 for (_, ok, _) in results if ok)
        fail_count = len(failures)

        # Report back to admin
        if fail_count == 0:
            await update.message.reply_text(
                f"✅ پیام همگانی با موفقیت برای {success_count} کاربر ارسال شد.\n\n🏠 منوی اصلی:",
                reply_markup=admin_menu_keyboard() if user_id in AUTHORIZED_USERS else get_main_menu_for_user(user_id),
            )
        else:
            # include a short sample of failed recipients
            sample = ", ".join(str(rid) for rid, _ in failures[:8])
            await update.message.reply_text(
                f"⚠️ ارسال برای {success_count} کاربر موفق بود، ولی {fail_count} ارسال ناموفق داشت.\nنمونه خطاها: {sample}\n\n🏠 منوی اصلی:",
                reply_markup=admin_menu_keyboard() if user_id in AUTHORIZED_USERS else get_main_menu_for_user(user_id),
            )
        return

    if context.user_data.get("awaiting_cookie"):
        context.user_data["cookie"] = text
        context.user_data.pop("awaiting_cookie", None)

        selected_courses = context.user_data.get("selected_courses", [])
        if not selected_courses:
            await update.message.reply_text(
                "⚠️ لیست دروس خالی است!", reply_markup=get_main_menu_for_user(user_id)
            )
            return

        telegram_user_id = str(chat_id)
        cookie = context.user_data["cookie"]

        # اتصال به دیتابیس برای گرفتن کد دانشجویی
        session = SessionLocal()
        try:
            student = (
                session.query(StudentStatus)
                .filter_by(telegram_user_id=telegram_user_id)
                .first()
            )
            if not student or not student.student_number:
                await update.message.reply_text(
                    "❌ کد دانشجویی شما در پایگاه داده یافت نشد.",
                    reply_markup=get_main_menu_for_user(user_id),
                )
                return
            stno = student.student_number
        except Exception as e:
            await update.message.reply_text(
                f"❌ خطا در بازیابی اطلاعات دانشجویی:\n{e}",
                reply_markup=get_main_menu_for_user(user_id),
            )
            return
        finally:
            session.close()

        # تبدیل selected_courses به فرمت مورد انتظار
        course_list = []
        for item in selected_courses:
            ins_view = "4" if item["action"] == "انتخاب واحد" else "5"
            operation = "register" if item["action"] == "انتخاب واحد" else "delete"
            course_list.append(
                {
                    "course": item["course_code"],
                    "group": item["group_code"],
                    "ins_view": ins_view,
                    "operation": operation,
                    "done": False,
                }
            )

        # شروع اجرای پس‌زمینه با قابلیت توقف (cancel_event)
        started = _start_run_for_chat(
            context,
            chat_id,
            target=main,
            args_tuple=(stno, TERM_CODE, cookie, course_list, chat_id),
        )

        if not started:
            await update.message.reply_text(
                "⚠️ یک عملیات درحال اجراست. لطفاً ابتدا آن را متوقف کنید یا صبر کنید تمام شود."
            )
            return

        await update.message.reply_text(
            "✅ عملیات ثبت نهایی دروس درحال اجراست.\n\n"
            "درصورت موفقیت یا بروز خطا، اطلاع رسانی خواهد شد.",
            reply_markup=_cancel_keyboard(),
        )

        context.user_data.clear()
        return

    if text == "💳 خرید اشتراک":
        context.user_data.clear()

        message = (
            "💳 <b>هزینه اشتراک:</b> مبلغ <b>۱۵۰٬۰۰۰ تومان</b> برای هر ترم است.\n"
            "این مبلغ جهت بهره مندی از خدمات ربات و انجام فرآیند انتخاب واحد دریافت می‌شود.\n\n"
            "⚠️ <b>توجه مهم:</b>\n"
            "پرداخت بر اساس <b>کد دانشجویی ثبت شده</b> شما انجام می‌گیرد.\n"
            "در صورت وارد کردن اشتباه، <b>امکان بازگشت وجه وجود ندارد</b>.\n\n"
            "لطفاً پیش از ادامه، از صحت کد دانشجویی وارد شده خود در بخش اطلاعات دانشجویی اطمینان حاصل فرمایید.\n\n"
            "لطفاً یکی از گزینه‌های پرداخت را انتخاب کنید:"
        )

        await update.message.reply_text(
            message, parse_mode="HTML", reply_markup=payment_options_keyboard()
        )
        return

    if text == "💬 گزارش و انتقادات":
        context.user_data.clear()
        context.user_data["feedback_mode"] = True
        await update.message.reply_text(
            "💬 لطفاً نظرت رو بنویس:", reply_markup=back_home_keyboard()
        )
        return

    await update.message.reply_text(
        "دستور ناشناخته است یا در مرحله‌ی اشتباهی قرار دارید.",
        reply_markup=back_home_keyboard(),
    )
