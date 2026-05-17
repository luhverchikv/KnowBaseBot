# utils/pagination.py
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

def build_pagination_keyboard(current_page: int, total_pages: int, prefix: str) -> InlineKeyboardBuilder:
    """
    Создаёт inline-клавиатуру с кнопками навигации по страницам.
    :param current_page: текущая страница (начиная с 0)
    :param total_pages: всего страниц
    :param prefix: префикс для callback_data (например, "admin_users")
    """
    kb = InlineKeyboardBuilder()
    if total_pages > 1:
        row = []
        if current_page > 0:
            row.append(InlineKeyboardButton(text="◀️", callback_data=f"{prefix}:page:{current_page - 1}"))
        
        # Кнопка-индикатор (не кликабельная, но Telegram требует callback_data)
        row.append(InlineKeyboardButton(text=f"📄 {current_page + 1}/{total_pages}", callback_data="noop"))
        
        if current_page < total_pages - 1:
            row.append(InlineKeyboardButton(text="▶️", callback_data=f"{prefix}:page:{current_page + 1}"))
            
        kb.row(*row)
    return kb

