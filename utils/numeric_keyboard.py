# utils/numeric_keyboard.py
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

def numeric_keyboard(
    current: str = "",
    suffix: str = "",
    prefix: str = "num_input",
    show_confirm: bool = True
) -> InlineKeyboardMarkup:
    """
    Создаёт универсальную цифровую клавиатуру с поддержкой суффиксов.
    
    :param current: текущее значение для отображения
    :param suffix: суффикс (например, " МБ", " шт.", " в день")
    :param prefix: префикс для callback_data (чтобы различать разные инпуты)
    :param show_confirm: показывать ли кнопки "Сохранить/Отмена"
    """
    kb = InlineKeyboardBuilder()
    
    # Строка с текущим значением (некликабельная)
    display = f"{current or '—'}{suffix}" if current or suffix else "—"
    kb.button(text=f"📊 Текущее: {display}", callback_data="noop")
    
    # Цифры 1-9
    for i in range(1, 10):
        kb.button(text=str(i), callback_data=f"{prefix}:digit:{i}")
    
    # Десятичная точка, 0, назад
    kb.button(text=".", callback_data=f"{prefix}:dot")
    kb.button(text="0", callback_data=f"{prefix}:digit:0")
    kb.button(text="⌫", callback_data=f"{prefix}:backspace")
    
    # Кнопки управления
    if show_confirm:
        kb.button(text="❌ Отмена", callback_data=f"{prefix}:cancel")
        kb.button(text="✅ Сохранить", callback_data=f"{prefix}:confirm")
    
    # Раскладка: 1 кнопка (текущее) + 3 ряда по 3 цифры + 1 ряд (., 0, ⌫) + 1 ряд (отмена/сохранить)
    kb.adjust(1, 3, 3, 3, 3, 2)
    return kb.as_markup()

