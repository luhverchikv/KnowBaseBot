# menu/settings.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Импортируем асинхронные ORM функции вместо старого класса Database
from database.requests import (
    get_user_difficulty,
    set_user_difficulty,
    get_user_reminders,
    set_user_reminders
)

router = Router()

def settings_keyboard():
    """Клавиатура для меню настроек."""
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🧠 Уровень сложности", callback_data="settings_difficulty"))
    kb.row(InlineKeyboardButton(text="🔔 Напоминания", callback_data="settings_reminders"))
    kb.row(InlineKeyboardButton(text="❌ Закрыть", callback_data="close_callback"))
    return kb.as_markup()

def difficulty_keyboard():
    """Клавиатура выбора сложности."""
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="😊 Легкий", callback_data="diff_easy"),
        InlineKeyboardButton(text="🤔 Средний", callback_data="diff_medium"),
        InlineKeyboardButton(text="😈 Сложный", callback_data="diff_hard")
    )
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="settings_back_to_menu"))
    return kb.as_markup()

@router.message(F.text == "⚙️ Настройки")
async def settings_menu(message: Message):
    """Точка входа в настройки с отображением текущих параметров."""
    user_id = message.from_user.id
    
    # ✅ Нативно асинхронно получаем текущие значения из БД через ORM
    difficulty = await get_user_difficulty(user_id)
    reminders = await get_user_reminders(user_id)
    
    # Форматируем для красивого вывода
    diff_map = {"easy": "😊 Легкий", "medium": "🤔 Средний", "hard": "😈 Сложный"}
    diff_text = diff_map.get(difficulty, "🤔 Средний")
    remind_text = "🔔 Включены" if reminders == 1 else "🔕 Выключены"
    
    text = (
        "⚙️ <b>Настройки бота</b>\n\n"
        f"🧠 Уровень сложности: <b>{diff_text}</b>\n"
        f"🔔 Напоминания: <b>{remind_text}</b>\n\n"
        "Выберите параметр, который хотите изменить:"
    )
    await message.answer(text=text, reply_markup=settings_keyboard(), parse_mode="HTML")
    
    try:
        await message.delete()
    except Exception:
        pass

@router.callback_query(F.data == "settings_difficulty")
async def settings_difficulty(call: CallbackQuery):
    """Показывает текущий уровень сложности и кнопки выбора."""
    await call.answer()
    user_id = call.from_user.id
    
    difficulty = await get_user_difficulty(user_id)
    
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
    
    # ✅ Сохраняем в БД асинхронно
    await set_user_difficulty(user_id, difficulty)
    
    diff_names = {
        "easy": "😊 Легкий",
        "medium": "🤔 Средний", 
        "hard": "😈 Сложный"
    }
    selected_name = diff_names.get(difficulty, difficulty)
    
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
    
    # ✅ Получаем текущее значение из БД, инвертируем и сохраняем
    current = await get_user_reminders(user_id)
    new_val = 1 if current == 0 else 0
    await set_user_reminders(user_id, new_val)
    
    status = "✅ Включены (9:00)" if new_val == 1 else "❌ Выключены"
    await call.message.edit_text(
        f"🔔 <b>Управление напоминаниями</b>\n\n"
        f"Статус: {status}\n\n"
        f"Нажмите на кнопку ещё раз, чтобы изменить.",
        reply_markup=settings_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "settings_back_to_menu")
async def settings_back_to_menu(call: CallbackQuery):
    """Возврат назад в главное меню настроек из подменю сложностей."""
    await call.answer()
    user_id = call.from_user.id
    
    difficulty = await get_user_difficulty(user_id)
    reminders = await get_user_reminders(user_id)
    
    diff_map = {"easy": "😊 Легкий", "medium": "🤔 Средний", "hard": "😈 Сложный"}
    diff_text = diff_map.get(difficulty, "🤔 Средний")
    remind_text = "🔔 Включены" if reminders == 1 else "🔕 Выключены"
    
    text = (
        "⚙️ <b>Настройки бота</b>\n\n"
        f"🧠 Уровень сложности: <b>{diff_text}</b>\n"
        f"🔔 Напоминания: <b>{remind_text}</b>\n\n"
        "Выберите параметр, который хотите изменить:"
    )
    await call.message.edit_text(text=text, reply_markup=settings_keyboard(), parse_mode="HTML")
