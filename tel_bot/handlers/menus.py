from __future__ import annotations

from tel_bot.handlers.auth import is_admin
from tel_bot.keyboard import admin_menu_keyboard, main_menu_keyboard


def main_menu_for_user(user_id: int):
    return admin_menu_keyboard() if is_admin(user_id) else main_menu_keyboard()

