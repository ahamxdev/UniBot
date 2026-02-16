from telegram import ReplyKeyboardMarkup


def admin_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            ["➕ افزودن دانشجو"],
            ["📚 انتخاب واحد", "📋 عملیات در حال انجام"],
            ["📖 راهنمای بات"],
            ["💬 ارسال پیام همگانی"],
            ["🛠 مدیریت بات"]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )


def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            ["📚 انتخاب واحد"],
            ["📖 راهنمای بات"],
            ["💬 گزارش و انتقادات"]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )


def back_home_keyboard(custom_keyboard=None):
    keyboard = custom_keyboard if custom_keyboard else [["❌ انصراف"]]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def post_selection_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            ["➕ افزودن درس دیگر"],
            ["✅ نهایی کردن عملیات"],
            ["❌ انصراف"]
        ],
        resize_keyboard=True
    )

