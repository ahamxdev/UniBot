# handlers.py
"""
Telegram bot handlers and the message-queue consumer job.

This module:
  - Provides high-level command/message/callback handlers (PTB v20+ style).
  - Exposes a repeating JobQueue task to drain the outbound message queue.
  - Avoids creating an Application instance here; the entry point is responsible
    for building the Application, registering handlers, connecting the job, and running.

Usage from your entry point (e.g., bot.py):
    from handlers import (
        start, handle_message, button_handler, setup_message_queue_job
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    setup_message_queue_job(app)
"""

from __future__ import annotations

from typing import Optional, Tuple
from queue import Empty

import threading
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from tel_bot.keyboard import (
    main_menu_keyboard,
    admin_menu_keyboard,
    back_home_keyboard,
    post_selection_keyboard,
    payment_options_keyboard,
)
from tel_bot.config import ADMIN_CHAT_ID
from tel_bot.message_queue import message_queue
# from db.save_to_db import save_student_status
from db.models import StudentStatus
from db.db import SessionLocal
from main.main import main


# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------
TERM_CODE: int = 14041


# -------------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------------
def _is_admin(user_id: int) -> bool:
    """
    Return True if the given user_id is an admin according to ADMIN_CHAT_ID.
    ADMIN_CHAT_ID may be a single int or a collection of ints.
    """
    if isinstance(ADMIN_CHAT_ID, (list, set, tuple)):
        return user_id in ADMIN_CHAT_ID
    return user_id == ADMIN_CHAT_ID


def get_main_menu_for_user(user_id: int):
    """
    Return the appropriate main menu keyboard for the given user.
    Admins see the admin menu; others see the standard menu.
    """
    return admin_menu_keyboard() if _is_admin(user_id) else main_menu_keyboard()


def get_student_number_by_telegram_id(user_id: int) -> Optional[str]:
    """
    Look up the student's registered number (stno) by Telegram user_id.
    Returns the student number as a string if present; otherwise None.
    """
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


# -------------------------------------------------------------------
# JobQueue task: drain outbound message queue
# -------------------------------------------------------------------
async def message_queue_consumer(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Drain the outbound message queue on each tick and deliver messages.
    Use a per-tick cap to avoid flooding users if a large backlog exists.
    """
    max_per_tick = 50
    for _ in range(max_per_tick):
        try:
            item: Tuple[int, str] = message_queue.get_nowait()
        except Empty:
            break

        chat_id, message = item
        try:
            await context.bot.send_message(chat_id=chat_id, text=message)
        except Exception:
            # Ignore failures silently; optionally log in dev
            continue


def setup_message_queue_job(application) -> None:
    """
    Attach the repeating queue-consumer job to the given Application's JobQueue.
    Prevent overlapping runs and suppress APScheduler warnings.
    """
    application.job_queue.run_repeating(
        message_queue_consumer,
        interval=1.0,      # safer than 0.5s, avoids overlap
        first=1.0,
        name="mq_consumer",
        job_kwargs={
            "coalesce": True,        # merge missed runs
            "max_instances": 1,      # never run more than one instance at a time
            "misfire_grace_time": 5  # give a few seconds grace if one run is late
        },
    )


# -------------------------------------------------------------------
# Handlers
# -------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /start command handler:
    - If user already accepted terms, show the main menu.
    - Otherwise, present terms and a confirmation button.
    """
    user_id = update.effective_user.id
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


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    CallbackQuery handler:
    - Handles term selection, student info confirmation/edit, and unit select/remove actions.
    """
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    chat_id = query.message.chat.id
    data = query.data

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
        except Exception:
            # Consider logging the exception for observability.
            await context.bot.send_message(
                chat_id=chat_id, text="❌ خطایی در ذخیره اطلاعات رخ داد."
            )
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


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Text message handler:
    - Orchestrates the wizard flow (student info, course/group input, finalization).
    - Also handles feedback collection.
    """
    user_id = update.effective_user.id
    text = (update.message.text or "").strip()

    # Feedback flow
    if context.user_data.get("feedback_mode"):
        context.user_data["feedback_mode"] = False

        await update.message.reply_text("🙏 ممنون که نظرت رو گفتی!")

        user = update.effective_user
        username = f"@{user.username}" if user.username else f"ID:{user.id}"
        feedback = f"📩 انتقاد جدید از {username}:\n\n\"{text}\""

        try:
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=feedback)
        except Exception:
            pass
        return

    # Start / Terms
    if text == "/start":
        await start(update, context)
        return

    if text == "✅ مطالعه کرده و موافقت میکنم":
        context.user_data["agreed_to_terms"] = True
        await update.message.reply_text(
            "ممنون از موافقتت 🙏\n\n📌 حالا یکی از گزینه های زیر رو انتخاب کن 👇",
            reply_markup=get_main_menu_for_user(user_id),
        )
        return

    if text == "❌ انصراف":
        context.user_data.clear()
        await update.message.reply_text(
            "🏠 منوی اصلی:", reply_markup=get_main_menu_for_user(user_id)
        )
        return

    # Student info
    if text == "👨‍🎓 اطلاعات دانشجویی":
        context.user_data.clear()
        telegram_user_id = str(update.effective_chat.id)

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

    # Student code → term selection
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

    # Unit selection flow
    if text == "📚 انتخاب واحد":
        # Ensure student info exists
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

    if context.user_data.get("awaiting_cookie"):
        context.user_data["cookie"] = text
        context.user_data.pop("awaiting_cookie", None)

        selected_courses = context.user_data.get("selected_courses", [])
        if not selected_courses:
            await update.message.reply_text(
                "⚠️ لیست دروس خالی است!", reply_markup=get_main_menu_for_user(user_id)
            )
            return

        telegram_user_id = str(update.effective_chat.id)
        cookie = context.user_data["cookie"]

        # Fetch student data to get stno
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

        # Build the course operation list for main()
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

        # Run the main() process in a background thread
        threading.Thread(
            target=main,
            args=(stno, TERM_CODE, cookie, course_list, update.effective_chat.id),
            daemon=True,
        ).start()

        await update.message.reply_text(
            "✅ عملیات ثبت نهایی دروس درحال اجراست.\n\n"
            "درصورت موفقیت یا بروز خطا، اطلاع رسانی خواهد شد.",
            reply_markup=get_main_menu_for_user(user_id),
        )

        context.user_data.clear()
        return

    # Payment and feedback entry
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

    # Fallback
    await update.message.reply_text(
        "دستور ناشناخته است یا در مرحله‌ی اشتباهی قرار دارید.",
        reply_markup=back_home_keyboard(),
    )
