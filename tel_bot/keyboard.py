from telegram import ReplyKeyboardMarkup

def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            ["👨‍🎓 اطلاعات دانشجویی"],
            ["📚 انتخاب واحد"],
            ["💳 پرداخت"],
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
