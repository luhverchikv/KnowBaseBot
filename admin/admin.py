# admin/admin.py
import asyncio
import io
import math
from datetime import datetime, time, union_type_required_datetime_combine = datetime.combine
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, CallbackQuery, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from utils.filter import is_owner
from utils.pagination import build_pagination_keyboard
from utils.numeric_keyboard import numeric_keyboard
from utils.logger import logger
from admin.export import create_excel_report

# Импортируем нативные асинхронные функции работы с БД
from database.requests import (
    get_unread_feedback_count,
    get_total_users_count,
    get_questions_count_by_period,
    get_global_token_stats,
    get_users_paginated,
    get_user_profile_counters,
    get_user_limits_dict,
    update_user_limit_value,
    get_feedback_paginated,
    get_feedback_by_id,
    mark_feedback_read,
    delete_feedback_by_id,
    get_user_quiz_export_data_list
)

class LimitEditStates(StatesGroup):
    waiting_category = State()  # Выбор категории лимита
    waiting_value = State()     # Ввод нового значения

router = Router()
USERS_PER_PAGE = 10
FEEDBACK_PER_PAGE = 5

ADMIN_WELCOME = """
🔐 <b>Панель администратора</b>

Добро пожаловать, владелец бота!

🛠 <b>Доступные функции:</b>
• 📊 Статистика по пользователям
• ⚙️ Управление лимитами
• 🧹 Чтение и очистка логов

Выберите действие ниже или введите команду:
"""

def admin_keyboard(unread_count: int = 0):
    """Собирает inline-клавиатуру админ-панели."""
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
    kb.row(InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users"))
    feedback_text = "💬 Отзывы" + (f" ({unread_count})" if unread_count > 0 else "")
    kb.row(InlineKeyboardButton(text=feedback_text, callback_data="admin_feedback"))
    kb.row(InlineKeyboardButton(text="⚙️ Настройки лимитов", callback_data="admin_config_placeholder"))
    kb.row(InlineKeyboardButton(text="🪙 Токены за сутки", callback_data="admin_tokens_day"))
    kb.row(InlineKeyboardButton(text="❌ Закрыть панель", callback_data="admin_close"))
    return kb.as_markup()


@router.message(Command("admin"), is_owner)
async def admin_panel(message: Message):
    """Точка входа в админ-панель."""
    unread = await get_unread_feedback_count()
    await message.answer(
        text=ADMIN_WELCOME,
        reply_markup=admin_keyboard(unread),
        parse_mode="HTML"
    )
    try:
        await message.delete()
    except Exception:
        pass


@router.message(Command("admin"), ~is_owner)
async def admin_denied(message: Message):
    """Обработка попытки доступа не-владельца."""
    await message.answer("🔒 Доступ запрещён. Эта команда доступна только владельцу бота.")
    try:
        await message.delete()
    except Exception:
        pass


@router.callback_query(F.data == "admin_stats", is_owner)
async def admin_stats_handler(call: CallbackQuery):
    """Обработчик кнопки «Статистика»."""
    await call.answer()
    
    # Расчёт временных интервалов
    now = datetime.now()
    today_start = datetime.combine(now.date(), time.min)
    yesterday_start = today_start - timedelta(days=1)

    total_users = await get_total_users_count()
    today_qs = await get_questions_count_by_period(today_start, now)
    yesterday_qs = await get_questions_count_by_period(yesterday_start, today_start)
    token_stats = await get_global_token_stats(user_id=None)

    text = (
        f"📊 <b>Общая статистика</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"📅 Вопросов сгенерировано сегодня: <b>{today_qs}</b>\n"
        f"📅 Вопросов сгенерировано вчера: <b>{yesterday_qs}</b>\n\n"
        f"🪙 <b>Расход токенов (всё время):</b>\n"
        f"• 📝 Генерация вопросов: <b>{token_stats['generation']:,}</b>\n"
        f"• ✅ Оценка ответов: <b>{token_stats['evaluation']:,}</b>\n"
        f"• 📊 <b>Всего:</b> {token_stats['total']:,} токенов"
    )
    unread = await get_unread_feedback_count()
    await call.message.edit_text(text, reply_markup=admin_keyboard(unread), parse_mode="HTML")


@router.callback_query(F.data == "admin_close", is_owner)
async def admin_close(call: CallbackQuery):
    await call.answer()
    try:
        await call.message.delete()
    except Exception:
        pass


@router.callback_query(F.data == "admin_tokens_day", is_owner)
async def admin_tokens_day(call: CallbackQuery):
    """Токены за последние 24 часа."""
    await call.answer()
    stats = await get_global_token_stats(user_id=None, days=1)
    text = (
        f"🪙 <b>Токены за сутки</b>\n\n"
        f"📝 Генерация: <b>{stats['generation']:,}</b>\n"
        f"✅ Оценка: <b>{stats['evaluation']:,}</b>\n"
        f"📊 <b>Всего:</b> {stats['total']:,} токенов"
    )
    unread = await get_unread_feedback_count()
    await call.message.edit_text(text, reply_markup=admin_keyboard(unread), parse_mode="HTML")


@router.callback_query(F.data == "admin_users", is_owner)
@router.callback_query(F.data.startswith("admin_users:page:"), is_owner)
async def admin_users_handler(call: CallbackQuery):
    """Список пользователей с пагинацией."""
    await call.answer()
    
    page = 0
    if call.data.startswith("admin_users:page:"):
        try:
            page = int(call.data.split(":")[2])
        except (IndexError, ValueError):
            page = 0

    total_users = await get_total_users_count()
    total_pages = math.ceil(total_users / USERS_PER_PAGE) if total_users > 0 else 1
    offset = page * USERS_PER_PAGE

    users = await get_users_paginated(limit=USERS_PER_PAGE, offset=offset)

    kb = InlineKeyboardBuilder()
    for u_id in users:
        kb.row(InlineKeyboardButton(text=f"👤 {u_id}", callback_data=f"admin_user_info:{u_id}"))

    kb.attach(build_pagination_keyboard(page, total_pages, "admin_users"))
    kb.row(InlineKeyboardButton(text="🔙 В меню админа", callback_data="admin_back_to_menu"))

    text = f"👥 <b>Пользователи (стр. {page + 1}/{total_pages})</b>\n\nВсего в базе: <b>{total_users}</b>"
    await call.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")


@router.callback_query(F.data == "noop", is_owner)
async def noop_handler(call: CallbackQuery):
    await call.answer()


@router.callback_query(F.data.startswith("admin_user_info:"), is_owner)
async def admin_user_info_handler(call: CallbackQuery):
    """Отображает детальную статистику и лимиты выбранного пользователя."""
    await call.answer()
    
    try:
        user_id = int(call.data.split(":")[1])
    except (IndexError, ValueError):
        await call.message.answer("❌ Ошибка: некорректный ID пользователя.")
        return

    token_stats = await get_global_token_stats(user_id=user_id)
    total_questions, files_count = await get_user_profile_counters(user_id)
    limits = await get_user_limits_dict(user_id)

    text = (
        f"👤 <b>Профиль пользователя: {user_id}</b>\n\n"
        f"📊 <b>Статистика (всё время):</b>\n"
        f"• 🪙 Токенов использовано: <b>{token_stats['total']:,}</b>\n"
        f"• ❓ Вопросов сгенерировано: <b>{total_questions}</b>\n"
        f"• 📁 Файлов загружено: <b>{files_count}</b>\n\n"
        f"⚙️ <b>Текущие лимиты:</b>\n"
        f"• Вопросов/день: <b>{limits['max_questions_per_day']}</b>\n"
        f"• Макс. файлов: <b>{limits['max_files']}</b>\n"
        f"• Макс. размер файла: <b>{limits['max_file_size_mb']} МБ</b>"
    )

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✏️ Редактировать лимиты", callback_data=f"admin_edit_limits:{user_id}"))
    kb.row(InlineKeyboardButton(text="📊 Выгрузить отчёт (30 дней)", callback_data=f"admin_export:{user_id}"))
    kb.row(InlineKeyboardButton(text="🔙 К списку пользователей", callback_data="admin_users"))

    await call.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_edit_limits"), is_owner)
async def admin_edit_limits_start(call: CallbackQuery, state: FSMContext):
    """Начало редактирования лимитов: выбор категории."""
    await call.answer()
    
    try:
        user_id = int(call.data.split(":")[1])
    except (IndexError, ValueError):
        await call.message.answer("❌ Ошибка: некорректный ID пользователя.")
        return
    
    await state.update_data(edit_user_id=user_id)
    limits = await get_user_limits_dict(user_id)
    
    text = (
        "✏️ <b>Редактирование лимитов</b>\n\n"
        "Выберите категорию для изменения:\n\n"
        f"• 📁 Макс. файлов: <b>{limits['max_files']}</b>\n"
        f"• 📦 Макс. размер: <b>{limits['max_file_size_mb']} МБ</b>\n"
        f"• ❓ Вопросов/день: <b>{limits['max_questions_per_day']}</b>"
    )
    
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="📁 Лимит файлов", callback_data="limit_cat:max_files"))
    kb.row(InlineKeyboardButton(text="📦 Размер файла", callback_data="limit_cat:max_file_size_mb"))
    kb.row(InlineKeyboardButton(text="❓ Вопросы/день", callback_data="limit_cat:max_questions_per_day"))
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data=f"admin_user_info:{user_id}"))
    
    await call.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await state.set_state(LimitEditStates.waiting_category)


@router.callback_query(F.data.startswith("limit_cat:"), is_owner)
async def admin_limit_category_selected(call: CallbackQuery, state: FSMContext):
    """Выбор категории лимита — показ цифровой клавиатуры."""
    await call.answer()
    
    data = await state.get_data()
    user_id = data.get("edit_user_id")
    if not user_id:
        await call.message.answer("❌ Ошибка сессии. Начните заново.")
        await state.clear()
        return
    
    field = call.data.split(":")[1]
    await state.update_data(edit_field=field)
    
    limits = await get_user_limits_dict(user_id)
    current = limits.get(field, 0)
    
    suffix_map = {
        "max_files": " шт.",
        "max_file_size_mb": " МБ",
        "max_questions_per_day": " в день"
    }
    suffix = suffix_map.get(field, "")
    input_prefix = f"limit_input:{user_id}:{field}"
    
    text = (
        f"✏️ <b>Изменение: {field}</b>\n\n"
        f"Текущее значение: <b>{current}{suffix}</b>\n\n"
        "Введите новое значение с помощью клавиатуры:"
    )
    
    await call.message.edit_text(
        text,
        reply_markup=numeric_keyboard(
            current=str(current),
            suffix=suffix,
            prefix=input_prefix,
            show_confirm=True
        ),
        parse_mode="HTML"
    )
    await state.set_state(LimitEditStates.waiting_value)


@router.callback_query(F.data.startswith("limit_input:"), is_owner)
async def admin_numeric_input_handler(call: CallbackQuery, state: FSMContext):
    """Обработчик ввода на встроенной цифровой клавиатуре."""
    await call.answer()
    
    data = await state.get_data()
    user_id = data.get("edit_user_id")
    field = data.get("edit_field")
    current_value = data.get("input_buffer", "")
    
    parts = call.data.split(":")
    if len(parts) < 4:
        return
    
    action = parts[3]
    
    if action == "cancel":
        await state.clear()
        await call.message.edit_text(
            "❌ Редактирование отменено.",
            reply_markup=InlineKeyboardBuilder().row(
                InlineKeyboardButton(text="🔙 В профиль", callback_data=f"admin_user_info:{user_id}")
            ).as_markup()
        )
        return
    
    elif action == "confirm":
        if not current_value:
            await call.answer("⚠️ Введите значение перед сохранением!", show_alert=True)
            return
        
        try:
            if field == "max_file_size_mb":
                new_value = float(current_value)
                if new_value < 0.1 or new_value > 100:
                    raise ValueError("Допустимый диапазон: 0.1–100 МБ")
            else:
                new_value = int(float(current_value))
                if new_value < 1 or new_value > 1000:
                    raise ValueError("Допустимый диапазон: 1–1000")
            
            await update_user_limit_value(user_id, field, new_value)
            await call.message.edit_text(
                f"✅ Лимит <b>{field}</b> обновлён: <b>{new_value}</b>",
                reply_markup=InlineKeyboardBuilder().row(
                    InlineKeyboardButton(text="🔙 В профиль", callback_data=f"admin_user_info:{user_id}")
                ).as_markup(),
                parse_mode="HTML"
            )
        except ValueError as e:
            await call.answer(f"⚠️ {e}", show_alert=True)
            return
        finally:
            await state.clear()
        return
    
    if action == "digit":
        current_value += parts[4]
    elif action == "dot" and "." not in current_value:
        current_value += "."
    elif action == "backspace":
        current_value = current_value[:-1]
    
    await state.update_data(input_buffer=current_value)
    
    suffix_map = {"max_files": " шт.", "max_file_size_mb": " МБ", "max_questions_per_day": " в день"}
    suffix = suffix_map.get(field, "")
    input_prefix = f"limit_input:{user_id}:{field}"
    
    await call.message.edit_text(
        call.message.text.split("Введите новое значение")[0] + 
        f"Текущий ввод: <b>{current_value or '—'}{suffix}</b>\n\n"
        "Введите новое значение с помощью клавиатуры:",
        reply_markup=numeric_keyboard(
            current=current_value,
            suffix=suffix,
            prefix=input_prefix,
            show_confirm=True
        ),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_feedback", is_owner)
async def admin_feedback_list(call: CallbackQuery):
    await call.answer()
    await _show_feedback_page(call, page=0)


async def _show_feedback_page(call: CallbackQuery, page: int):
    """Внутренняя функция пагинации отзывов."""
    offset = page * FEEDBACK_PER_PAGE
    feedbacks = await get_feedback_paginated(limit=FEEDBACK_PER_PAGE, offset=offset)
    
    if not feedbacks:
        unread = await get_unread_feedback_count()
        await call.message.edit_text(
            "📭 <b>Отзывов пока нет.</b>",
            reply_markup=admin_keyboard(unread),
            parse_mode="HTML"
        )
        return
    
    text = f"💬 <b>Отзывы (стр. {page + 1})</b>\n\n"
    for fb_id, user_db_id, fb_text, created_at, tg_id in feedbacks:
        display_id = tg_id if tg_id else f"user_{user_db_id}"
        preview = fb_text[:100] + ("..." if len(fb_text) > 100 else "")
        text += f"👤 <code>{display_id}</code> • <i>{created_at}</i>\n{preview}\n\n"
    
    kb = InlineKeyboardBuilder()
    for fb_id, user_db_id, fb_text, created_at, tg_id in feedbacks:
        kb.row(InlineKeyboardButton(text=f"👁 {tg_id or f'user_{user_db_id}'}", callback_data=f"feedback_view:{fb_id}"))
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"feedback_page:{page-1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"📄 {page+1}", callback_data="noop"))
    if len(feedbacks) == FEEDBACK_PER_PAGE:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"feedback_page:{page+1}"))
        
    kb.row(*nav_buttons)
    kb.row(InlineKeyboardButton(text="🔙 В меню админа", callback_data="admin_back_to_menu"))
    await call.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("feedback_page:"), is_owner)
async def admin_feedback_page_change(call: CallbackQuery):
    await call.answer()
    try:
        page = int(call.data.split(":")[1])
    except (IndexError, ValueError):
        page = 0
    await _show_feedback_page(call, page)


@router.callback_query(F.data.startswith("feedback_view:"), is_owner)
async def admin_feedback_view(call: CallbackQuery):
    await call.answer()
    try:
        fb_id = int(call.data.split(":")[1])
    except (IndexError, ValueError):
        return
    
    row = await get_feedback_by_id(fb_id)
    if not row:
        await call.answer("❌ Отзыв не найден", show_alert=True)
        return
    
    user_db_id, fb_text, created_at, is_read = row
    if not is_read:
        await mark_feedback_read(fb_id)
    
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"feedback_delete:{fb_id}"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_feedback")
    )
    
    await call.message.edit_text(
        f"💬 <b>Полный отзыв</b>\n\n"
        f"👤 User DB ID: <code>{user_db_id}</code>\n"
        f"🕒 Дата: <i>{created_at}</i>\n\n"
        f"📝 <b>Текст:</b>\n<code>{fb_text}</code>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("feedback_delete:"), is_owner)
async def admin_feedback_delete(call: CallbackQuery):
    await call.answer()
    try:
        fb_id = int(call.data.split(":")[1])
    except (IndexError, ValueError):
        return
    
    await delete_feedback_by_id(fb_id)
    await call.answer("✅ Отзыв удалён", show_alert=True)
    await _show_feedback_page(call, page=0)


@router.callback_query(F.data == "admin_back_to_menu", is_owner)
async def admin_back_to_menu(call: CallbackQuery):
    await call.answer()
    unread = await get_unread_feedback_count()
    await call.message.edit_text(text=ADMIN_WELCOME, reply_markup=admin_keyboard(unread), parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_export:"))
async def handle_export_request(callback: CallbackQuery):
    """Генерация и отправка Excel-отчёта для пользователя."""
    await callback.answer()
    
    try:
        target_user_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.message.edit_text("❌ Ошибка: неверный ID пользователя")
        return
    
    progress_msg = await callback.message.edit_text(
        f"⏳ Формирую отчёт за 30 дней для пользователя {target_user_id}...\n\nЭто может занять некоторое время."
    )
    
    try:
        # Получаем данные через асинхронную функцию
        data = await get_user_quiz_export_data_list(user_id=target_user_id, days=30)
        
        if not data:
            await progress_msg.edit_text(f"⚠️ У пользователя {target_user_id} нет результатов за последние 30 дней.")
            return
        
        # Генерация Excel (если библиотека openpyxl внутри create_excel_report синхронная, 
        # имеет смысл оставить её выполнение в потоке, чтобы не вешать event loop)
        excel_file = await asyncio.to_thread(
            create_excel_report,
            data=data,
            user_id=target_user_id,
            period_days=30
        )
        
        await callback.message.answer_document(
            document=BufferedInputFile(
                file=excel_file.getvalue(),
                filename=f"KnowBase_Report_User{target_user_id}.xlsx"
            ),
            caption=(
                f"📊 **Отчёт пользователя {target_user_id}**\n\n"
                f"• Период: последние 30 дней\n"
                f"• Вопросов: {len(data)}\n"
                f"_Откройте в Excel, Google Таблицах или LibreOffice_"
            ),
            parse_mode="Markdown"
        )
        
        await progress_msg.edit_text("✅ Отчёт успешно сформирован и отправлен!")
        logger.info(f"📤 Export sent for user {target_user_id}: {len(data)} records")
        
    except Exception as e:
        logger.error(f"❌ Export error for user {target_user_id}: {e}")
        await progress_msg.edit_text(f"❌ Ошибка при генерации отчёта:\n`{str(e)[:200]}`")
