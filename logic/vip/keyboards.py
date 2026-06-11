# logic/vip/keyboards.py
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def vip_menu_keyboard():
    """Клавиатура VIP-меню"""
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="⭐ Премиум на 30 дней (150 Stars)", callback_data="vip_buy_30")
    )
    kb.row(
        InlineKeyboardButton(text="⭐ Премиум на 90 дней (400 Stars)", callback_data="vip_buy_90")
    )
    kb.row(
        InlineKeyboardButton(text="❌ Закрыть", callback_data="close_callback")
    )
    return kb.as_markup()

def vip_confirm_keyboard(days: int, price: int):
    """Клавиатура подтверждения покупки"""
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text=f"💎 Оплатить {price} Stars", pay=True)
    )
    kb.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="vip_cancel")
    )
    return kb.as_markup()

