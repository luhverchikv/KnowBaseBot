# menu/settings.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()

def settings_keyboard():
    """Клавиатура для меню настроек."""
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🧠 Уровень сложности", callback_data="settings_difficulty"))
    kb.row(InlineKeyboardButton(text="🔔 Напоминания", callback_data="settings_reminders"))
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="settings_back"))
    return kb.as_markup()

@router.message(F.text == "⚙️ Настройки")
async def settings_menu(message: Message):
    """Точка входа в настройки."""
    await message.answer(
        "⚙️ <b>Настройки бота</b>\n\n"
        "Выберите параметр, который хотите изменить:",
        reply_markup=settings_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "settings_difficulty")
async def settings_difficulty(call: CallbackQuery):
    """Заглушка для изменения сложности."""
    await call.answer()
    await call.message.edit_text(
        "🧠 <b>Уровень сложности</b>\n\n"
        "Здесь можно будет выбрать:\n"
        "• Легкий\n"
        "• Средний\n"
        "• Сложный\n\n"
        "Функция в разработке.",
        reply_markup=settings_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "settings_reminders")
async def settings_reminders(call: CallbackQuery):
    """Заглушка для напоминаний."""
    await call.answer()
    await call.message.edit_text(
        "🔔 <b>Напоминания</b>\n\n"
        "Здесь можно будет настроить:\n"
        "• Время напоминания\n"
        "• Частоту уведомлений\n\n"
        "Функция в разработке.",
        reply_markup=settings_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "settings_back")
async def settings_back(call: CallbackQuery):
    """Возврат в главное меню."""
    await call.answer()
    from menu.start_menu import start_keyboard
    await call.message.edit_text(
        "🔙 Вы вернулись в главное меню.",
        reply_markup=start_keyboard()
    )

