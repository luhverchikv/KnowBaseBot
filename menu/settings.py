# menu/settings.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from logic.manage.db import Database
import asyncio

router = Router()
db = Database()

def settings_keyboard():
    """Клавиатура для меню настроек."""
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🧠 Уровень сложности", callback_data="settings_difficulty"))
    kb.row(InlineKeyboardButton(text="🔔 Напоминания", callback_data="settings_reminders"))
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="settings_back"))
    return kb.as_markup()

def difficulty_keyboard():
    """Клавиатура выбора сложности."""
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="😊 Легкий", callback_data="diff_easy"),
        InlineKeyboardButton(text="🤔 Средний", callback_data="diff_medium"),
        InlineKeyboardButton(text="😈 Сложный", callback_data="diff_hard")
    )
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
    """Показывает текущий уровень сложности и кнопки выбора."""
    await call.answer()
    user_id = call.from_user.id
    
    # Получаем текущую сложность
    difficulty = await asyncio.to_thread(db.get_user_difficulty, user_id)
    
    diff_names = {
        "easy": "😊 Легкий",
        "medium": "🤔 Средний",
        "hard": "😈 Сложный"
    }
    current_name = diff_names.get(difficulty, "🤔 Средний")
    
    await call.message.edit_text(
        f"🧠 <b>Уровень сложности</b>\n\n"
        f"Текущий уровень: <b>{current_name}</b>\n\n"
        "Выберите новый уровень:",
        reply_markup=difficulty_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("diff_"))
async def handle_difficulty_selection(call: CallbackQuery):
    """Обработчик выбора новой сложности."""
    await call.answer()
    user_id = call.from_user.id
    difficulty = call.data.split("_")[1]  # easy, medium, hard
    
    # Сохраняем в БД
    await asyncio.to_thread(db.set_user_difficulty, user_id, difficulty)
    
    diff_names = {
        "easy": "😊 Легкий",
        "medium": "🤔 Средний", 
        "hard": "😈 Сложный"
    }
    selected_name = diff_names.get(difficulty, difficulty)
    
    # Показываем подтверждение и возвращаемся в меню настроек
    await call.message.edit_text(
        f"✅ Уровень сложности изменён на: <b>{selected_name}</b>\n\n"
        "Теперь вопросы будут генерироваться с учётом этого уровня.",
        reply_markup=settings_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "settings_reminders")
async def settings_reminders(call: CallbackQuery):
    """Переключает напоминания вкл/выкл."""
    await call.answer()
    user_id = call.from_user.id
    
    # Получаем текущее значение и инвертируем
    current = await asyncio.to_thread(db.get_user_reminders, user_id)
    new_val = 1 if current == 0 else 0
    await asyncio.to_thread(db.set_user_reminders, user_id, new_val)
    
    status = "✅ Включены (9:00)" if new_val == 1 else "❌ Выключены"
    await call.message.edit_text(
        f"🔔 <b>Управление напоминаниями</b>\n\n"
        f"Статус: {status}\n\n"
        f"Нажмите на кнопку ещё раз, чтобы изменить.",
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

