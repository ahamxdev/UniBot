from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

from config import TOKEN, ADMIN_CHAT_ID

def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            ["📚 انتخاب واحد"],
            ["🔄 عملیات در حال انجام"],
            ["💳 پرداخت"],
            ["💬 انتقادات"],
            ["👨‍🎓اطلاعات دانشجویی"]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

def back_home_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[["🏠 بازگشت به خانه"]],
        resize_keyboard=True
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("✅ موافقم", callback_data="agree")]]
    await update.message.reply_text(
        "سلام! 👋\nبرای ادامه، لطفاً با شرایط موافقت کن.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id
    data = query.data

    if data == "agree":
        await context.bot.send_message(
            chat_id=chat_id,
            text="ممنون از موافقتت 🙏 حالا یکی از گزینه‌های زیر رو انتخاب کن:",
            reply_markup=main_menu_keyboard()
        )

    elif data.startswith("term_"):
        selected_term = data.replace("term_", "")
        student_code = context.user_data.get("student_code", "نامشخص")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ ترم {selected_term} انتخاب شد.\n\n📌 اطلاعات شما:\nکد دانشجویی: {student_code}\nترم: {selected_term}\n\n🏠 به منوی اصلی برگشتی.",
            reply_markup=main_menu_keyboard()
        )
        context.user_data.clear()

    elif data == "select_unit":
        await context.bot.send_message(chat_id=chat_id, text="✅ اطلاعات شما ثبت شد.")
        context.user_data.clear()
        await context.bot.send_message(chat_id=chat_id, text="🏠 به منوی اصلی برگشتی.", reply_markup=main_menu_keyboard())

    elif data == "remove_unit":
        await context.bot.send_message(chat_id=chat_id, text="✅ اطلاعات شما ثبت شد.")
        context.user_data.clear()
        await context.bot.send_message(chat_id=chat_id, text="🏠 به منوی اصلی برگشتی.", reply_markup=main_menu_keyboard())

    elif data == "back_home":
        context.user_data.clear()
        await context.bot.send_message(chat_id=chat_id, text="🏠 برگشتی به خانه.", reply_markup=main_menu_keyboard())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    chat_id = update.message.chat.id
    text = update.message.text.strip()

    if text == "/start":
        await start(update, context)
        return

    if text == "🏠 بازگشت به خانه":
        context.user_data.clear()
        await update.message.reply_text("🏠 برگشتی به خانه.", reply_markup=main_menu_keyboard())
        return

    if context.user_data.get("feedback_mode"):
        context.user_data["feedback_mode"] = False
        await update.message.reply_text("🙏 ممنون که نظرت رو گفتی!")
        username = f"@{user.username}" if user.username else f"ID:{user.id}"
        feedback = f"📩 انتقاد جدید از {username}:\n\n\"{text}\""
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=feedback)
        return

    if context.user_data.get("awaiting_student_code"):
        if text == "🏠 بازگشت به خانه":
            context.user_data.clear()
            await update.message.reply_text("🏠 برگشتی به خانه.", reply_markup=main_menu_keyboard())
            return

        if not text.isdigit():
            await update.message.reply_text("⚠️ لطفاً فقط عدد وارد کن. کد دانشجویی باید عدد باشد.")
            return

        context.user_data["student_code"] = text
        context.user_data["awaiting_student_code"] = False
        keyboard = [[InlineKeyboardButton("14041", callback_data="term_14041")]]
        await update.message.reply_text(
            "✅ کد دانشجویی دریافت شد. ترم را انتخاب کن:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if text == "📚 انتخاب واحد":
        context.user_data.clear()
        context.user_data["awaiting_course_code"] = True
        await update.message.reply_text(
            "📘 لطفاً کد درس را وارد کن:",
            reply_markup=back_home_keyboard()
        )
        return

    if context.user_data.get("awaiting_course_code"):
        if text == "🏠 بازگشت به خانه":
            context.user_data.clear()
            await update.message.reply_text("🏠 برگشتی به خانه.", reply_markup=main_menu_keyboard())
            return

        if not text.isdigit():
            await update.message.reply_text("⚠️ لطفاً فقط عدد وارد کن. کد درس باید عدد باشد.")
            return

        context.user_data["course_code"] = text
        context.user_data["awaiting_course_code"] = False
        context.user_data["awaiting_group_code"] = True

        await update.message.reply_text(
            "✍️ لطفاً کد گروه رو وارد کن:",
            reply_markup=back_home_keyboard()
        )
        return

    if context.user_data.get("awaiting_group_code"):
        if text == "🏠 بازگشت به خانه":
            context.user_data.clear()
            await update.message.reply_text("🏠 برگشتی به خانه.", reply_markup=main_menu_keyboard())
            return

        if not text.isdigit():
            await update.message.reply_text("⚠️ لطفاً فقط عدد وارد کن. کد گروه باید عدد باشد.")
            return

        context.user_data["group_code"] = text
        context.user_data["awaiting_group_code"] = False

        keyboard = [
            [InlineKeyboardButton("1 انتخاب", callback_data="select_unit")],
            [InlineKeyboardButton("2 حذف واحد", callback_data="remove_unit")],
            [InlineKeyboardButton("🏠 بازگشت به خانه", callback_data="back_home")]
        ]

        await update.message.reply_text(
            "✅ لطفاً یکی از گزینه‌های زیر را انتخاب کن:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if text == "💳 پرداخت":
        await update.message.reply_text("💳 در حال انتقال به زرین‌پال...\nhttps://zarinpal.com/pg/")

    elif text == "💬 انتقادات":
        context.user_data["feedback_mode"] = True
        await update.message.reply_text("💬 لطفاً نظرت رو بنویس:", reply_markup=back_home_keyboard())

    elif text == "🔄 عملیات در حال انجام":
        await update.message.reply_text("🔄 عملیات‌های در حال انجام اینجا نمایش داده می‌شن.")

    elif text == "👨‍🎓اطلاعات دانشجویی":
        context.user_data.clear()
        context.user_data["awaiting_student_code"] = True
        await update.message.reply_text("👤 لطفاً کد دانشجویی خود را وارد کن:", reply_markup=back_home_keyboard())

    else:
        await update.message.reply_text(f"تو گفتی: {text}", reply_markup=back_home_keyboard())

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 ربات روشنه!")
    app.run_polling()
