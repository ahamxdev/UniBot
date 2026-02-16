from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from tel_bot.handlers.admin import build_operations_view, handle_admin_callback, handle_admin_text
from tel_bot.handlers.auth import is_admin, is_authorized
from tel_bot.handlers.db_access import get_active_access
from tel_bot.handlers.menus import main_menu_for_user
from tel_bot.handlers.run_registry import (
    cancel_run_for_chat,
    get_run,
    prune_runs_for_chat,
)
from tel_bot.handlers.settings import TERM_CODE
from tel_bot.handlers.state import clear_transient_state
from tel_bot.handlers.texts import TERMS_TEXT
from tel_bot.handlers.user import handle_user_callback, handle_user_text
from tel_bot.keyboard import back_home_keyboard


async def _send_access_banner(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if is_admin(user_id):
        return

    access = get_active_access(user_id)
    if not access:
        return

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            "✅ دسترسی شما فعال است.\n\n"
            f"🎓 کد دانشجویی: <b>{access.student_number}</b>\n"
            f"📚 سقف انتخاب واحد: <b>{access.max_courses}</b> درس\n"
            f"🗓 کد ترم: <b>{TERM_CODE}</b>"
        ),
        parse_mode="HTML",
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⚠️ شما اجازه دسترسی به این بات را ندارید.")
        return

    if context.user_data.get("agreed_to_terms"):
        await _send_access_banner(update, context)
        await update.message.reply_text(
            "🏠 منوی اصلی:",
            reply_markup=main_menu_for_user(user_id),
        )
        return

    await update.message.reply_text(
        text=TERMS_TEXT,
        parse_mode="HTML",
        reply_markup=back_home_keyboard([["✅ مطالعه کرده و موافقت میکنم"]]),
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    try:
        await query.answer()
    except Exception:
        pass

    user_id = query.from_user.id
    if not is_authorized(user_id):
        return

    chat_id = query.message.chat.id
    data = query.data or ""

    if data.startswith("cancel_run"):
        run_id = data.split(":", 1)[1] if ":" in data else None
        ok = cancel_run_for_chat(context, chat_id, run_id=run_id)
        if ok:
            stno = None
            if run_id:
                run = get_run(context, chat_id, run_id)
                stno = run.get("student_number") if run else None

            text = "⛔️ عملیات متوقف شد. لطفاً چند لحظه صبر کنید."
            if stno:
                text = f"⛔️ عملیات برای کد دانشجویی {stno} متوقف شد. لطفاً چند لحظه صبر کنید."
            await context.bot.send_message(chat_id=chat_id, text=text)
        else:
            await context.bot.send_message(chat_id=chat_id, text="ℹ️ عملیات فعالی برای توقف یافت نشد.")
        return

    if data == "admin_ops" and is_admin(user_id):
        text, markup = build_operations_view(context, chat_id)
        try:
            await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=markup)
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", reply_markup=markup)
        return

    if is_admin(user_id):
        handled = await handle_admin_callback(update, context)
        if handled:
            return

    handled = await handle_user_callback(update, context)
    if handled:
        return


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()

    prune_runs_for_chat(context, chat_id)

    if not is_authorized(user_id):
        await update.message.reply_text("⚠️ شما اجازه دسترسی به این بات را ندارید.")
        return

    if text == "✅ مطالعه کرده و موافقت میکنم":
        context.user_data["agreed_to_terms"] = True
        await _send_access_banner(update, context)
        await update.message.reply_text(
            "ممنون از موافقتت 🙏\n\n📌 حالا یکی از گزینه‌های زیر را انتخاب کن 👇",
            reply_markup=main_menu_for_user(user_id),
        )
        return

    if not context.user_data.get("agreed_to_terms"):
        await update.message.reply_text("برای شروع لطفاً /start را بزن و شرایط را تایید کن.")
        return

    if text == "❌ انصراف":
        if not is_admin(user_id):
            cancel_run_for_chat(context, chat_id)
        clear_transient_state(context)
        await update.message.reply_text("🏠 منوی اصلی:", reply_markup=main_menu_for_user(user_id))
        return

    if is_admin(user_id):
        handled = await handle_admin_text(update, context)
        if handled:
            return

    handled = await handle_user_text(update, context)
    if handled:
        return

    await update.message.reply_text(
        "دستور ناشناخته است یا در مرحله‌ی اشتباهی قرار دارید.",
        reply_markup=back_home_keyboard(),
    )
