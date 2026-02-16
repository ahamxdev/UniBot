from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from main.main import main as run_unit_selection
from tel_bot.handlers.auth import notify_admins
from tel_bot.handlers.db_access import get_active_access, get_student_status
from tel_bot.handlers.menus import main_menu_for_user
from tel_bot.handlers.run_registry import cancel_keyboard, start_run_for_chat
from tel_bot.handlers.settings import TERM_CODE
from tel_bot.handlers.state import clear_transient_state
from tel_bot.keyboard import back_home_keyboard, post_selection_keyboard

def _get_student_profile(user_id: int) -> tuple[str | None, int | None]:
    access = get_active_access(user_id)
    if access:
        return access.student_number, access.max_courses

    status = get_student_status(user_id)
    if status:
        return status.student_number, None

    return None, None


def _limit_reached(context: ContextTypes.DEFAULT_TYPE, max_courses: int | None) -> bool:
    if not max_courses:
        return False
    selected = context.user_data.get("selected_courses") or []
    return len(selected) >= max_courses


async def handle_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    query = update.callback_query
    if not query:
        return False

    user_id = query.from_user.id
    chat_id = query.message.chat.id
    data = query.data or ""

    if data in {"select_unit", "remove_unit"}:
        course_code = context.user_data.get("course_code")
        group_code = context.user_data.get("group_code")
        if not course_code or not group_code:
            await context.bot.send_message(
                chat_id=chat_id,
                text="⚠️ لطفاً دوباره از ابتدا اطلاعات درس را وارد کنید.",
                reply_markup=back_home_keyboard(),
            )
            return True

        student_number, max_courses = _get_student_profile(user_id)
        if student_number is None:
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ اطلاعات شما در سیستم ثبت نشده است. لطفاً با ادمین هماهنگ کنید.",
                reply_markup=main_menu_for_user(user_id),
            )
            clear_transient_state(context)
            return True

        if _limit_reached(context, max_courses):
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ شما فقط مجاز به ثبت {max_courses} درس هستید.\n"
                     "لطفاً عملیات را نهایی کنید یا با ادمین هماهنگ کنید.",
                reply_markup=post_selection_keyboard(),
            )
            context.user_data.pop("course_code", None)
            context.user_data.pop("group_code", None)
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

    if data == "back_home":
        clear_transient_state(context)
        await context.bot.send_message(
            chat_id=chat_id,
            text="🏠 منوی اصلی:",
            reply_markup=main_menu_for_user(user_id),
        )
        return True

    return False


async def handle_user_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.message:
        return False

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()

    # --- Feedback flow ---
    if context.user_data.get("feedback_mode"):
        context.user_data.pop("feedback_mode", None)

        user = update.effective_user
        username = f"@{user.username}" if user.username else f"ID:{user.id}"
        feedback = f"📩 انتقاد جدید از {username}:\n\n\"{text}\""

        await notify_admins(context.bot, feedback)

        await update.message.reply_text(
            "🙏 ممنون که نظرت رو گفتی!\n\n🏠 منوی اصلی:",
            reply_markup=main_menu_for_user(user_id),
        )
        return True

    if text == "📚 انتخاب واحد":
        student_number, max_courses = _get_student_profile(user_id)
        if student_number is None:
            await update.message.reply_text(
                "❌ اکانت شما فعال نیست یا اطلاعات شما ثبت نشده است.\n"
                "اگر فکر می‌کنید اشتباه است، با ادمین هماهنگ کنید.",
                reply_markup=main_menu_for_user(user_id),
            )
            return True

        if max_courses is not None and max_courses <= 0:
            await update.message.reply_text(
                "⚠️ سقف انتخاب واحد برای شما ۰ ثبت شده است.\n"
                "لطفاً با ادمین هماهنگ کنید.",
                reply_markup=main_menu_for_user(user_id),
            )
            return True

        clear_transient_state(context)
        context.user_data["selected_courses"] = []
        context.user_data["awaiting_course_code"] = True
        await update.message.reply_text(
            "📘 لطفاً کد درس را وارد کن:",
            reply_markup=back_home_keyboard(),
        )
        return True

    if context.user_data.get("awaiting_course_code"):
        if not text.isdigit():
            await update.message.reply_text(
                "⚠️ مقدار کد درس معتبر نیست!\n\nلطفاً فقط عدد وارد کن.",
                reply_markup=back_home_keyboard(),
            )
            return True

        student_number, max_courses = _get_student_profile(user_id)
        if _limit_reached(context, max_courses):
            await update.message.reply_text(
                f"⚠️ شما فقط مجاز به ثبت {max_courses} درس هستید.\n"
                "لطفاً عملیات را نهایی کنید.",
                reply_markup=post_selection_keyboard(),
            )
            context.user_data["awaiting_course_code"] = False
            return True

        context.user_data["course_code"] = text
        context.user_data["awaiting_course_code"] = False
        context.user_data["awaiting_group_code"] = True
        await update.message.reply_text(
            "✍️ لطفاً کد گروه را وارد کن:",
            reply_markup=back_home_keyboard(),
        )
        return True

    if context.user_data.get("awaiting_group_code"):
        if not text.isdigit():
            await update.message.reply_text(
                "⚠️ مقدار کد گروه معتبر نیست!\n\nلطفاً فقط عدد وارد کن.",
                reply_markup=back_home_keyboard(),
            )
            return True

        context.user_data["group_code"] = text
        context.user_data["awaiting_group_code"] = False

        inline_buttons = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ انتخاب واحد", callback_data="select_unit")],
                [InlineKeyboardButton("❌ حذف واحد", callback_data="remove_unit")],
            ]
        )
        await update.message.reply_text(
            "✅ لطفاً یکی از گزینه‌های زیر را انتخاب کن:",
            reply_markup=inline_buttons,
        )
        return True

    if text == "➕ افزودن درس دیگر":
        student_number, max_courses = _get_student_profile(user_id)
        if _limit_reached(context, max_courses):
            await update.message.reply_text(
                f"⚠️ شما فقط مجاز به ثبت {max_courses} درس هستید.\n"
                "لطفاً عملیات را نهایی کنید.",
                reply_markup=post_selection_keyboard(),
            )
            return True

        context.user_data["awaiting_course_code"] = True
        await update.message.reply_text(
            "📘 لطفاً کد درس جدید را وارد کن:",
            reply_markup=back_home_keyboard(),
        )
        return True

    if text == "✅ نهایی کردن عملیات":
        selected_courses = context.user_data.get("selected_courses") or []
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
            summary
            + "\n\n🧠 حالا لطفاً کوکی مرورگر خود را برای انجام عملیات وارد کن:",
            reply_markup=back_home_keyboard(),
        )
        return True

    if context.user_data.get("awaiting_cookie"):
        cookie = text
        context.user_data.pop("awaiting_cookie", None)

        selected_courses = context.user_data.get("selected_courses") or []
        if not selected_courses:
            await update.message.reply_text(
                "⚠️ لیست دروس خالی است!",
                reply_markup=main_menu_for_user(user_id),
            )
            return True

        student_number, _ = _get_student_profile(user_id)
        if student_number is None:
            await update.message.reply_text(
                "❌ اطلاعات شما در سیستم یافت نشد. لطفاً با ادمین هماهنگ کنید.",
                reply_markup=main_menu_for_user(user_id),
            )
            clear_transient_state(context)
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

        run_id = start_run_for_chat(
            context,
            chat_id,
            target=run_unit_selection,
            args=(student_number, TERM_CODE, cookie, course_list, chat_id, ""),
            student_number=student_number,
            course_list=course_list,
        )
        if not run_id:
            await update.message.reply_text(
                "⚠️ یک عملیات در حال اجراست. لطفاً ابتدا آن را متوقف کنید یا صبر کنید تمام شود.",
                reply_markup=cancel_keyboard(),
            )
            return True

        await update.message.reply_text(
            "✅ عملیات در حال اجراست.\n"
            "در صورت موفقیت یا بروز خطا، اطلاع رسانی خواهد شد.",
            reply_markup=cancel_keyboard(run_id),
        )
        clear_transient_state(context)
        return True

    if text == "💬 گزارش و انتقادات":
        clear_transient_state(context)
        context.user_data["feedback_mode"] = True
        await update.message.reply_text(
            "💬 لطفاً نظرت رو بنویس:",
            reply_markup=back_home_keyboard(),
        )
        return True

    if text == "👨‍🎓 اطلاعات دانشجویی":
        await update.message.reply_text(
            "ℹ️ ثبت اطلاعات دانشجویی توسط ادمین انجام می‌شود و این بخش حذف شده است.",
            reply_markup=main_menu_for_user(user_id),
        )
        return True

    if text == "📖 راهنمای بات":
        await update.message.reply_text(
            "📖 راهنمای سریع:\n\n"
            "1) از گزینه «📚 انتخاب واحد» درس‌ها را اضافه کن.\n"
            "2) بعد از «✅ نهایی کردن عملیات»، کوکی مرورگر سامانه آموزش را ارسال کن.\n"
            "3) عملیات به‌صورت خودکار انجام می‌شود و نتیجه هر درس اعلام می‌گردد.\n\n"
            "⚠️ کوکی را فقط از مرورگرِ وارد شده به سامانه بردار.",
            reply_markup=main_menu_for_user(user_id),
        )
        return True

    return False
