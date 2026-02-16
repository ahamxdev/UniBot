from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from tel_bot.handlers.db_access import (
    list_active_student_user_ids,
    list_active_user_ids_by_student_number,
    upsert_student_access,
)
from tel_bot.handlers.menus import main_menu_for_user
from tel_bot.handlers.run_registry import get_runs_for_chat, start_run_for_chat
from tel_bot.handlers.settings import TERM_CODE
from tel_bot.handlers.state import clear_transient_state
from tel_bot.keyboard import back_home_keyboard, post_selection_keyboard

from main.main import main as run_unit_selection


_BROADCAST_CONCURRENCY = 8
_ADMIN_UNIT_STEP_KEY = "admin_unit_step"
_ADMIN_TARGET_STNO_KEY = "admin_target_student_number"


def _is_add_student_flow(context: ContextTypes.DEFAULT_TYPE) -> bool:
    return bool(context.user_data.get("admin_add_student_step"))


def _is_admin_unit_flow(context: ContextTypes.DEFAULT_TYPE) -> bool:
    return bool(context.user_data.get(_ADMIN_UNIT_STEP_KEY)) or bool(context.user_data.get(_ADMIN_TARGET_STNO_KEY))


def _run_actions_keyboard(run_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ عملیات جدید", callback_data="admin_new_op")],
            [InlineKeyboardButton("📋 عملیات", callback_data="admin_ops")],
            [InlineKeyboardButton("⛔️ توقف این عملیات", callback_data=f"cancel_run:{run_id}")],
        ]
    )


def build_operations_view(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> tuple[str, InlineKeyboardMarkup | None]:
    runs = get_runs_for_chat(context, chat_id)
    if not runs:
        return "ℹ️ هیچ عملیاتی برای نمایش وجود ندارد.", None

    status_label = {
        "running": "درحال اجرا",
        "completed": "تمام شد",
        "canceled": "متوقف شد",
        "error": "خطا",
    }

    lines: list[str] = ["<b>📋 عملیات‌ها</b>\n"]
    buttons: list[list[InlineKeyboardButton]] = []

    for i, data in enumerate(runs, 1):
        stno = data.get("student_number") or "نامشخص"
        raw_status = data.get("status")
        status = status_label.get(raw_status, "نامشخص")
        if raw_status == "running":
            try:
                if data.get("cancel_event") and data["cancel_event"].is_set():
                    status = "درحال توقف"
            except Exception:
                pass

        course_list = data.get("course_list") or []
        total = len(course_list)
        done = sum(1 for c in course_list if c.get("done")) if total else 0
        progress = f"{done}/{total}" if total else "—"

        started_at = data.get("started_at")
        started_str = datetime.fromtimestamp(float(started_at)).strftime("%H:%M:%S") if started_at else "—"

        lines.append(f"{i}) 🎓 <b>{stno}</b> | وضعیت: <b>{status}</b> | پیشرفت: <b>{progress}</b> | شروع: <b>{started_str}</b>")

        if data.get("status") == "running":
            buttons.append([InlineKeyboardButton(f"⛔️ توقف {stno}", callback_data=f"cancel_run:{data['id']}")])

    buttons.append([InlineKeyboardButton("🔄 بروزرسانی", callback_data="admin_ops")])
    buttons.append([InlineKeyboardButton("➕ عملیات جدید", callback_data="admin_new_op")])
    buttons.append([InlineKeyboardButton("🏠 منوی اصلی", callback_data="back_home")])

    return "\n".join(lines), InlineKeyboardMarkup(buttons)


async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    query = update.callback_query
    if not query:
        return False

    chat_id = query.message.chat.id
    data = query.data or ""

    if data == "admin_new_op":
        clear_transient_state(context)
        context.user_data[_ADMIN_UNIT_STEP_KEY] = "student_number"
        context.user_data["selected_courses"] = []
        await context.bot.send_message(
            chat_id=chat_id,
            text="🎓 لطفاً کد دانشجویی را وارد کن:",
            reply_markup=back_home_keyboard(),
        )
        return True

    if data in {"select_unit", "remove_unit"} and _is_admin_unit_flow(context):
        course_code = context.user_data.get("course_code")
        group_code = context.user_data.get("group_code")
        if not course_code or not group_code:
            await context.bot.send_message(
                chat_id=chat_id,
                text="⚠️ لطفاً دوباره از ابتدا اطلاعات درس را وارد کنید.",
                reply_markup=back_home_keyboard(),
            )
            return True

        action_text = "انتخاب واحد" if data == "select_unit" else "حذف واحد"
        symbol = "✅" if data == "select_unit" else "❌"

        context.user_data.setdefault("selected_courses", []).append(
            {"course_code": course_code, "group_code": group_code, "action": action_text}
        )

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{symbol} {action_text} ثبت شد.\nدرس: {course_code}\nگروه: {group_code}",
            reply_markup=post_selection_keyboard(),
        )

        context.user_data.pop("course_code", None)
        context.user_data.pop("group_code", None)
        return True

    return False


async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.message:
        return False

    user_id = update.effective_user.id
    text = (update.message.text or "").strip()

    # --- Start add-student flow ---
    if text == "➕ افزودن دانشجو":
        clear_transient_state(context)
        context.user_data["admin_add_student_step"] = "telegram_user_id"
        context.user_data["admin_new_student"] = {}
        await update.message.reply_text(
            "👤 لطفاً آیدی عددی تلگرام دانشجو را وارد کن:\n"
            "(مثال: 123456789)",
            reply_markup=back_home_keyboard(),
        )
        return True

    # --- Admin unit selection flow entry ---
    if text == "📚 انتخاب واحد":
        clear_transient_state(context)
        context.user_data[_ADMIN_UNIT_STEP_KEY] = "student_number"
        context.user_data["selected_courses"] = []
        await update.message.reply_text(
            "🎓 لطفاً کد دانشجویی را وارد کن:",
            reply_markup=back_home_keyboard(),
        )
        return True

    if text == "📋 عملیات در حال انجام":
        view_text, markup = build_operations_view(context, update.effective_chat.id)
        await update.message.reply_text(view_text, parse_mode="HTML", reply_markup=markup)
        return True

    # --- Add-student flow steps ---
    if _is_add_student_flow(context):
        step = context.user_data.get("admin_add_student_step")
        payload: dict[str, Any] = context.user_data.get("admin_new_student") or {}

        if step == "telegram_user_id":
            if not text.isdigit():
                await update.message.reply_text("⚠️ فقط عدد وارد کن (Telegram User ID).")
                return True
            payload["telegram_user_id"] = str(int(text))
            context.user_data["admin_new_student"] = payload
            context.user_data["admin_add_student_step"] = "student_number"
            await update.message.reply_text("🎓 لطفاً کد دانشجویی را وارد کن:")
            return True

        if step == "student_number":
            if not text.isdigit():
                await update.message.reply_text("⚠️ کد دانشجویی معتبر نیست. فقط عدد وارد کن.")
                return True
            payload["student_number"] = text
            context.user_data["admin_new_student"] = payload
            context.user_data["admin_add_student_step"] = "max_courses"
            await update.message.reply_text("📚 لطفاً تعداد درسی که مجاز است انتخاب کند را وارد کن:")
            return True

        if step == "max_courses":
            if not text.isdigit():
                await update.message.reply_text("⚠️ تعداد درس معتبر نیست. فقط عدد وارد کن.")
                return True
            max_courses = int(text)
            if max_courses <= 0:
                await update.message.reply_text("⚠️ تعداد درس باید بزرگتر از ۰ باشد.")
                return True

            telegram_user_id = payload.get("telegram_user_id")
            student_number = payload.get("student_number")
            if not telegram_user_id or not student_number:
                clear_transient_state(context)
                await update.message.reply_text(
                    "❌ اطلاعات ناقص است. لطفاً دوباره تلاش کن.",
                    reply_markup=main_menu_for_user(user_id),
                )
                return True

            try:
                upsert_student_access(
                    telegram_user_id=telegram_user_id,
                    student_number=student_number,
                    max_courses=max_courses,
                    is_active=True,
                )
            except Exception:
                clear_transient_state(context)
                await update.message.reply_text(
                    "❌ خطا در ذخیره‌سازی اطلاعات. لطفاً دوباره تلاش کن.",
                    reply_markup=main_menu_for_user(user_id),
                )
                return True

            clear_transient_state(context)
            await update.message.reply_text(
                "✅ دانشجو با موفقیت ثبت/به‌روزرسانی شد.\n\n"
                f"👤 User ID: <b>{telegram_user_id}</b>\n"
                f"🎓 کد دانشجویی: <b>{student_number}</b>\n"
                f"📚 سقف درس: <b>{max_courses}</b>",
                parse_mode="HTML",
                reply_markup=main_menu_for_user(user_id),
            )
            return True

        return True

    # --- Admin unit selection flow steps ---
    if context.user_data.get(_ADMIN_UNIT_STEP_KEY) == "student_number":
        if not text.isdigit():
            await update.message.reply_text("⚠️ کد دانشجویی معتبر نیست. فقط عدد وارد کن.")
            return True

        context.user_data[_ADMIN_TARGET_STNO_KEY] = text
        context.user_data[_ADMIN_UNIT_STEP_KEY] = None
        context.user_data["awaiting_course_code"] = True
        await update.message.reply_text("📘 لطفاً کد درس را وارد کن:", reply_markup=back_home_keyboard())
        return True

    if context.user_data.get("awaiting_course_code") and _is_admin_unit_flow(context):
        if not text.isdigit():
            await update.message.reply_text("⚠️ مقدار کد درس معتبر نیست! فقط عدد وارد کن.")
            return True

        context.user_data["course_code"] = text
        context.user_data["awaiting_course_code"] = False
        context.user_data["awaiting_group_code"] = True
        await update.message.reply_text("✍️ لطفاً کد گروه را وارد کن:", reply_markup=back_home_keyboard())
        return True

    if context.user_data.get("awaiting_group_code") and _is_admin_unit_flow(context):
        if not text.isdigit():
            await update.message.reply_text("⚠️ مقدار کد گروه معتبر نیست! فقط عدد وارد کن.")
            return True

        context.user_data["group_code"] = text
        context.user_data["awaiting_group_code"] = False

        inline_buttons = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ انتخاب واحد", callback_data="select_unit")],
                [InlineKeyboardButton("❌ حذف واحد", callback_data="remove_unit")],
            ]
        )
        await update.message.reply_text("✅ لطفاً یکی از گزینه‌های زیر را انتخاب کن:", reply_markup=inline_buttons)
        return True

    if text == "➕ افزودن درس دیگر" and _is_admin_unit_flow(context):
        context.user_data["awaiting_course_code"] = True
        await update.message.reply_text("📘 لطفاً کد درس جدید را وارد کن:", reply_markup=back_home_keyboard())
        return True

    if text == "✅ نهایی کردن عملیات" and _is_admin_unit_flow(context):
        selected_courses = context.user_data.get("selected_courses", [])
        if not selected_courses:
            await update.message.reply_text(
                "⚠️ هنوز درسی ثبت نشده است!",
                reply_markup=main_menu_for_user(user_id),
            )
            return True

        summary_lines = ["📚 لیست نهایی عملیات:"]
        for i, course in enumerate(selected_courses, 1):
            summary_lines.append(
                f"{i}. درس {course['course_code']} - گروه {course['group_code']} ({course['action']})"
            )
        summary = "\n".join(summary_lines)

        context.user_data["awaiting_cookie"] = True
        await update.message.reply_text(
            summary + "\n\n🧠 حالا لطفاً کوکی مرورگر را برای انجام عملیات ارسال کن:",
            reply_markup=back_home_keyboard(),
        )
        return True

    if context.user_data.get("awaiting_cookie") and _is_admin_unit_flow(context):
        cookie = text
        context.user_data.pop("awaiting_cookie", None)

        selected_courses = context.user_data.get("selected_courses", [])
        if not selected_courses:
            await update.message.reply_text("⚠️ لیست دروس خالی است!", reply_markup=main_menu_for_user(user_id))
            return True

        stno = context.user_data.get(_ADMIN_TARGET_STNO_KEY)
        if not stno:
            clear_transient_state(context)
            await update.message.reply_text("❌ کد دانشجویی مشخص نیست. لطفاً دوباره تلاش کن.", reply_markup=main_menu_for_user(user_id))
            return True

        course_list: list[dict] = []
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

        recipients: list[int] = [update.effective_chat.id]
        recipients.extend(list_active_user_ids_by_student_number(stno))
        recipients = list(dict.fromkeys(recipients))  # keep order, unique

        run_id = start_run_for_chat(
            context,
            update.effective_chat.id,
            target=run_unit_selection,
            args=(stno, TERM_CODE, cookie, course_list, recipients, f"🎓 {stno} | "),
            student_number=stno,
            course_list=course_list,
            allow_multiple=True,
        )
        if not run_id:
            await update.message.reply_text(
                "❌ خطا در شروع عملیات. لطفاً دوباره تلاش کن.",
                reply_markup=main_menu_for_user(user_id),
            )
            clear_transient_state(context)
            return True

        await update.message.reply_text(
            f"✅ عملیات برای کد دانشجویی <b>{stno}</b> شروع شد.\n"
            "برای شروع عملیات جدید دوباره «📚 انتخاب واحد» را بزن.\n"
            "برای دیدن وضعیت عملیات‌ها «📋 عملیات در حال انجام» را بزن.",
            parse_mode="HTML",
            reply_markup=_run_actions_keyboard(run_id),
        )

        clear_transient_state(context)
        return True

    # --- Start broadcast flow ---
    if text == "💬 ارسال پیام همگانی":
        context.user_data["broadcast_mode"] = True
        await update.message.reply_text(
            "✍️ لطفاً پیام همگانی را ارسال کن (متن/عکس/ویدیو/فایل).",
            reply_markup=back_home_keyboard(),
        )
        return True

    # --- Broadcast payload ---
    if context.user_data.get("broadcast_mode"):
        context.user_data.pop("broadcast_mode", None)

        recipients = list_active_student_user_ids()
        if not recipients:
            await update.message.reply_text(
                "ℹ️ هیچ دانشجوی فعالی برای ارسال پیام یافت نشد.",
                reply_markup=main_menu_for_user(user_id),
            )
            return True

        msg = update.message

        kind = "text"
        payload: dict[str, Any] = {"text": (msg.text or "").strip()}

        if msg.photo:
            kind = "photo"
            payload = {"file_id": msg.photo[-1].file_id, "caption": (msg.caption or "").strip()}
        elif msg.video:
            kind = "video"
            payload = {"file_id": msg.video.file_id, "caption": (msg.caption or "").strip()}
        elif msg.document:
            kind = "document"
            payload = {
                "file_id": msg.document.file_id,
                "filename": msg.document.file_name,
                "caption": (msg.caption or "").strip(),
            }

        sem = asyncio.Semaphore(_BROADCAST_CONCURRENCY)

        async def _send_one(recipient_id: int) -> tuple[int, bool, str]:
            try:
                async with sem:
                    if kind == "text":
                        await context.bot.send_message(chat_id=recipient_id, text=payload["text"])
                    elif kind == "photo":
                        await context.bot.send_photo(
                            chat_id=recipient_id,
                            photo=payload["file_id"],
                            caption=payload.get("caption") or None,
                        )
                    elif kind == "video":
                        await context.bot.send_video(
                            chat_id=recipient_id,
                            video=payload["file_id"],
                            caption=payload.get("caption") or None,
                        )
                    elif kind == "document":
                        await context.bot.send_document(
                            chat_id=recipient_id,
                            document=payload["file_id"],
                            caption=payload.get("caption") or None,
                        )
                    else:
                        await context.bot.send_message(chat_id=recipient_id, text=payload.get("text", ""))
                return (recipient_id, True, "")
            except Exception as e:
                return (recipient_id, False, str(e))

        results = await asyncio.gather(*(_send_one(uid) for uid in recipients))

        failures = [(rid, err) for (rid, ok, err) in results if not ok]
        success_count = sum(1 for (_, ok, _) in results if ok)
        fail_count = len(failures)

        if fail_count == 0:
            await update.message.reply_text(
                f"✅ پیام همگانی برای {success_count} کاربر ارسال شد.\n\n🏠 منوی اصلی:",
                reply_markup=main_menu_for_user(user_id),
            )
        else:
            sample = ", ".join(str(rid) for rid, _ in failures[:8])
            await update.message.reply_text(
                f"⚠️ ارسال برای {success_count} کاربر موفق بود، ولی {fail_count} ارسال ناموفق داشت.\n"
                f"نمونه: {sample}\n\n🏠 منوی اصلی:",
                reply_markup=main_menu_for_user(user_id),
            )
        return True

    return False
