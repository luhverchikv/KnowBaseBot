# admin/admin.py
import asyncio
import io
import math
from datetime import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, CallbackQuery, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.filter import is_owner
from logic.manage.db import Database
from utils.pagination import build_pagination_keyboard
from utils.numeric_keyboard import numeric_keyboard
from utils.logger import logger
from aiogram.exceptions import TelegramBadRequest
from admin.export import create_excel_report

router = Router()
db = Database()
USERS_PER_PAGE = 10
FEEDBACK_PER_PAGE = 5

# Текст приветствия администратора
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
    """Собирает inline-клавиатуру админ-панели (каждая кнопка в отдельном ряду)."""
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
    kb.row(InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users"))
    feedback_text = f"💬 Отзывы" + (f" ({unread_count})" if unread_count > 0 else "")
    kb.row(InlineKeyboardButton(text=feedback_text, callback_data="admin_feedback"))
    kb.row(InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_config"))
    kb.row(InlineKeyboardButton(text="🪙 Токены за сутки", callback_data="admin_tokens_day"))
    kb.row(InlineKeyboardButton(text="❌ Закрыть панель", callback_data="admin_close"))
    return kb.as_markup()


@router.message(Command("admin"), is_owner)
async def admin_panel(message: Message):
    """Точка входа в админ-панель (только для owner_id)."""
    unread = await asyncio.to_thread(db.get_unread_feedback_count)
    await message.answer(
        text=ADMIN_WELCOME,
        reply_markup=admin_keyboard(unread),
        parse_mode="HTML"
    )
    await message.delete()


@router.message(Command("admin"), ~is_owner)
async def admin_denied(message: Message):
    """Обработка попытки доступа не-владельца к /admin."""
    await message.answer("🔒 Доступ запрещён. Эта команда доступна только владельцу бота.")
    await message.delete()
    

@router.callback_query(F.data == "admin_stats", is_owner)
async def admin_stats_handler(call: CallbackQuery):
    """Обработчик кнопки «Статистика»."""
    await call.answer()
    
    # Асинхронные запросы к БД (не блокируем event loop)
    total_users = await asyncio.to_thread(db.get_total_users_count)
    today_qs = await asyncio.to_thread(db.get_questions_count_today)
    yesterday_qs = await asyncio.to_thread(db.get_questions_count_yesterday)
    
    # ✅ Статистика токенов (за всё время)
    token_stats = await asyncio.to_thread(db.get_token_stats, user_id=None)  # None = все пользователи

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
    # Обновляем сообщение, сохраняя клавиатуру
    await call.message.edit_text(text, reply_markup=admin_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "admin_close", is_owner)
async def admin_back(call: CallbackQuery):
    await call.answer()
    await call.message.delete()


@router.callback_query(F.data == "admin_tokens_day", is_owner)
async def admin_tokens_day(call: CallbackQuery):
    """Токены за последние 24 часа."""
    await call.answer()
    stats = await asyncio.to_thread(db.get_token_stats, user_id=None, days=1)
    text = (
        f"🪙 <b>Токены за сутки</b>\n\n"
        f"📝 Генерация: <b>{stats['generation']:,}</b>\n"
        f"✅ Оценка: <b>{stats['evaluation']:,}</b>\n"
        f"📊 <b>Всего:</b> {stats['total']:,} токенов"
    )
    await call.message.edit_text(text, reply_markup=admin_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "admin_users", is_owner)
@router.callback_query(F.data.startswith("admin_users:page:"), is_owner)
async def admin_users_handler(call: CallbackQuery):
    """Список пользователей с пагинацией."""
    await call.answer()
    
    # Определяем текущую страницу
    page = 0
    if call.data.startswith("admin_users:page:"):
        try:
            page = int(call.data.split(":")[2])
        except (IndexError, ValueError):
            page = 0

    total_users = await asyncio.to_thread(db.get_total_users_count)
    total_pages = math.ceil(total_users / USERS_PER_PAGE) if total_users > 0 else 1
    offset = page * USERS_PER_PAGE

    users = await asyncio.to_thread(db.get_users_paginated, limit=USERS_PER_PAGE, offset=offset)

    kb = InlineKeyboardBuilder()
    for (u_id,) in users:
        kb.row(InlineKeyboardButton(text=f"👤 {u_id}", callback_data=f"admin_user_info:{u_id}"))

    kb.attach(build_pagination_keyboard(page, total_pages, "admin_users"))
    kb.row(InlineKeyboardButton(text="🔙 В меню админа", callback_data="admin_back_to_menu"))

    text = f"👥 <b>Пользователи (стр. {page + 1}/{total_pages})</b>\n\nВсего в базе: <b>{total_users}</b>"
    await call.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")


@router.callback_query(F.data == "admin_back_to_menu", is_owner)
async def admin_back_to_menu(call: CallbackQuery):
    """Возврат в главное меню админки."""
    await call.answer()
    await call.message.edit_text(text=ADMIN_WELCOME, reply_markup=admin_keyboard(), parse_mode="HTML")
    
    
@router.callback_query(F.data == "noop", is_owner)
async def noop_handler(call: CallbackQuery):
    """Заглушка для клика по индикатору страницы (чтобы Telegram не ругался)."""
    await call.answer()
    

@router.callback_query(F.data.startswith("admin_user_info:"), is_owner)
async def admin_user_info_handler(call: CallbackQuery):
    """Отображает детальную статистику и лимиты выбранного пользователя."""
    await call.answer()
    
    # Извлекаем user_id из callback_data
    try:
        user_id = int(call.data.split(":")[1])
    except (IndexError, ValueError):
        await call.message.answer("❌ Ошибка: некорректный ID пользователя.")
        return

    # Асинхронно собираем данные
    token_stats = await asyncio.to_thread(db.get_token_stats, user_id)
    total_questions = await asyncio.to_thread(db.get_user_total_questions, user_id)
    files_count = await asyncio.to_thread(db.get_user_files_count, user_id)
    limits = await asyncio.to_thread(db.get_user_limits, user_id)

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
    kb.row(InlineKeyboardButton(text="🔙 В меню админа", callback_data="admin_back_to_menu"))

    await call.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")





# admin/admin.py (добавить в начало файла)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# ... после импортов ...

class LimitEditStates(StatesGroup):
    waiting_category = State()  # Выбор категории лимита
    waiting_value = State()     # Ввод нового значения

# ... внутри admin.py, после существующих хендлеров ...

@router.callback_query(F.data.startswith("admin_edit_limits"), is_owner)
async def admin_edit_limits_start(call: CallbackQuery, state: FSMContext):
    """Начало редактирования лимитов: выбор категории."""
    await call.answer()
    
    # Извлекаем user_id из предыдущего callback_data (admin_user_info:123456)
    try:
        user_id = int(call.data.split(":")[1])
    except (IndexError, ValueError):
        await call.message.answer("❌ Ошибка: некорректный ID пользователя.")
        return
    
    await state.update_data(edit_user_id=user_id)
    
    limits = await asyncio.to_thread(db.get_user_limits, user_id)
    
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
    """Пользователь выбрал категорию лимита — показываем цифровую клавиатуру."""
    await call.answer()
    
    data = await state.get_data()
    user_id = data.get("edit_user_id")
    if not user_id:
        await call.message.answer("❌ Ошибка сессии. Начните заново.")
        await state.clear()
        return
    
    field = call.data.split(":")[1]  # max_files, max_file_size_mb, ...
    await state.update_data(edit_field=field)
    
    # Получаем текущее значение и суффикс
    limits = await asyncio.to_thread(db.get_user_limits, user_id)
    current = limits.get(field, 0)
    
    suffix_map = {
        "max_files": " шт.",
        "max_file_size_mb": " МБ",
        "max_questions_per_day": " в день"
    }
    suffix = suffix_map.get(field, "")
    
    # Формируем префикс для callback_data (уникальный для этого инпута)
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
    """Обработчик нажатий на цифровой клавиатуре."""
    await call.answer()
    
    data = await state.get_data()
    user_id = data.get("edit_user_id")
    field = data.get("edit_field")
    current_value = data.get("input_buffer", "")
    
    # Парсим callback_data: limit_input:123456:max_files:digit:5
    parts = call.data.split(":")
    if len(parts) < 4:
        return
    
    action = parts[3]  # digit, dot, backspace, confirm, cancel
    
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
        # Сохраняем значение
        if not current_value:
            await call.answer("⚠️ Введите значение перед сохранением!", show_alert=True)
            return
        
        try:
            # Определяем тип значения
            if field == "max_file_size_mb":
                new_value = float(current_value)
                if new_value < 0.1 or new_value > 100:
                    raise ValueError("Допустимый диапазон: 0.1–100 МБ")
            else:
                new_value = int(float(current_value))  # int(3.9) = 3
                if new_value < 1 or new_value > 1000:
                    raise ValueError("Допустимый диапазон: 1–1000")
            
            # Обновляем в БД
            success = await asyncio.to_thread(db.update_user_limit, user_id, field, new_value)
            if success:
                await call.message.edit_text(
                    f"✅ Лимит <b>{field}</b> обновлён: <b>{new_value}</b>",
                    reply_markup=InlineKeyboardBuilder().row(
                        InlineKeyboardButton(text="🔙 В профиль", callback_data=f"admin_user_info:{user_id}")
                    ).as_markup(),
                    parse_mode="HTML"
                )
            else:
                await call.message.answer("❌ Ошибка обновления в БД.")
        except ValueError as e:
            await call.answer(f"⚠️ {e}", show_alert=True)
            return
        finally:
            await state.clear()
        return
    
    # Обновляем буфер ввода
    if action == "digit":
        digit = parts[4]
        current_value += digit
    elif action == "dot" and "." not in current_value:
        current_value += "."
    elif action == "backspace":
        current_value = current_value[:-1]
    
    await state.update_data(input_buffer=current_value)
    
    # Обновляем клавиатуру с новым текущим значением
    suffix_map = {
        "max_files": " шт.",
        "max_file_size_mb": " МБ",
        "max_questions_per_day": " в день"
    }
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
    """Список отзывов с пагинацией."""
    await call.answer()
    await _show_feedback_page(call, page=0)

async def _show_feedback_page(call: CallbackQuery, page: int):
    """Внутренняя функция для отображения страницы отзывов."""
    offset = page * FEEDBACK_PER_PAGE
    feedbacks = await asyncio.to_thread(db.get_feedback_paginated, limit=FEEDBACK_PER_PAGE, offset=offset)
    total = await asyncio.to_thread(db.get_unread_feedback_count)  # можно заменить на общий счётчик
    
    if not feedbacks:
        await call.message.edit_text(
            "📭 <b>Отзывов пока нет.</b>\n\n"
            "Как только пользователи напишут — они появятся здесь.",
            reply_markup=admin_keyboard(),
            parse_mode="HTML"
        )
        return
    
    # Формируем текст с отзывами
    text = f"💬 <b>Отзывы (стр. {page + 1})</b>\n\n"
    for fb_id, user_db_id, fb_text, created_at, tg_id in feedbacks:
        # tg_id может быть None, если пользователь удалён из users
        display_id = tg_id if tg_id else f"user_{user_db_id}"
        preview = fb_text[:100] + ("..." if len(fb_text) > 100 else "")
        text += f"👤 <code>{display_id}</code> • <i>{created_at}</i>\n{preview}\n\n"
    
    # Кнопки навигации
    kb = InlineKeyboardBuilder()
    for fb_id, user_db_id, fb_text, created_at, tg_id in feedbacks:
        kb.row(InlineKeyboardButton(
            text=f"👁 {tg_id or f'user_{user_db_id}'}",
            callback_data=f"feedback_view:{fb_id}"
        ))
    
    # Пагинация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"feedback_page:{page-1}"))
    
    nav_buttons.append(InlineKeyboardButton(text=f"📄 {page+1}", callback_data="noop"))
    
    if len(feedbacks) == FEEDBACK_PER_PAGE:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"feedback_page:{page+1}"))
    
    if nav_buttons:  # Добавляем ряд только если есть кнопки навигации
        kb.row(*nav_buttons)
    
    kb.row(InlineKeyboardButton(text="🔙 В меню админа", callback_data="admin_back_to_menu"))
    
    await call.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("feedback_page:"), is_owner)
async def admin_feedback_page_change(call: CallbackQuery):
    """Переключение страницы отзывов."""
    await call.answer()
    try:
        page = int(call.data.split(":")[1])
    except (IndexError, ValueError):
        page = 0
    await _show_feedback_page(call, page)

@router.callback_query(F.data.startswith("feedback_view:"), is_owner)
async def admin_feedback_view(call: CallbackQuery):
    """Просмотр полного текста отзыва."""
    await call.answer()
    try:
        fb_id = int(call.data.split(":")[1])
    except (IndexError, ValueError):
        await call.answer("❌ Ошибка ID", show_alert=True)
        return
    
    # Получаем полный отзыв
    db.cursor.execute(
        "SELECT user_id, feedback_text, created_at, is_read FROM feedback WHERE id = ?",
        (fb_id,)
    )
    row = db.cursor.fetchone()
    if not row:
        await call.answer("❌ Отзыв не найден", show_alert=True)
        return
    
    user_db_id, fb_text, created_at, is_read = row
    
    # Помечаем как прочитанный, если ещё нет
    if not is_read:
        await asyncio.to_thread(db.mark_feedback_read, fb_id)
    
    # Кнопки действий
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
    """Удаление отзыва."""
    await call.answer()
    try:
        fb_id = int(call.data.split(":")[1])
    except (IndexError, ValueError):
        return
    
    success = await asyncio.to_thread(db.delete_feedback, fb_id)
    if success:
        await call.answer("✅ Отзыв удалён", show_alert=True)
        # Возвращаемся к списку
        await _show_feedback_page(call, page=0)
    else:
        await call.answer("❌ Не удалось удалить", show_alert=True)

@router.callback_query(F.data == "admin_back_to_menu", is_owner)
async def admin_back_to_menu(call: CallbackQuery):
    """Возврат в главное меню админки."""
    await call.answer()
    unread = await asyncio.to_thread(db.get_unread_feedback_count)
    await call.message.edit_text(
        text=ADMIN_WELCOME,
        reply_markup=admin_keyboard(unread),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("admin_export:"))
async def handle_export_request(callback: CallbackQuery):
    """Генерация и отправка Excel-отчёта для пользователя."""
    await callback.answer()  # Убираем "часики"
    
    # Извлекаем user_id из callback_data
    try:
        target_user_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.message.edit_text("❌ Ошибка: неверный ID пользователя")
        return
    
    # 🔹 Уведомление о начале генерации
    progress_msg = await callback.message.edit_text(
        f"⏳ Формирую отчёт за 30 дней для пользователя {target_user_id}...\n\n"
        f"Это может занять до 30 секунд."
    )
    
    try:
        # 🔹 Получаем данные из БД (в потоке, чтобы не блокировать)
        data = await asyncio.to_thread(
            db.get_user_quiz_export_data, 
            user_id=target_user_id, 
            days=30
        )
        
        if not data:
            await progress_msg.edit_text(
                f"⚠️ У пользователя {target_user_id} нет результатов за последние 30 дней.",
                #reply_markup=admin_user_profile_keyboard(target_user_id)
            )
            return
        
        # 🔹 Генерируем Excel
        excel_file = await asyncio.to_thread(
            create_excel_report,
            data=data,
            user_id=target_user_id,
            period_days=30
        )
        
        # 🔹 Отправляем файл
        await callback.message.answer_document(
            document=BufferedInputFile(
                file=excel_file.getvalue(),
                filename=f"KnowBase_Report_User{target_user_id}.xlsx"
            ),
            caption=(
                f"📊 **Отчёт пользователя {target_user_id}**\n\n"
                f"• Период: последние 30 дней\n"
                f"• Вопросов: {len(data)}\n"
                f"• Файл создан: {data[0]['generated_at'][:10]} — {datetime.now().strftime('%Y-%m-%d')}\n\n"
                f"_Откройте в Excel, Google Таблицах или LibreOffice_"
            ),
            parse_mode="Markdown"
        )
        
        
        await progress_msg.edit_text(
            f"✅ Отчёт успешно сформирован и отправлен!",
            #reply_markup=admin_user_profile_keyboard(target_user_id)
        )
        
        logger.info(f"📤 Export sent for user {target_user_id}: {len(data)} records")
        
    except Exception as e:
        logger.error(f"❌ Export error for user {target_user_id}: {e}")
        await progress_msg.edit_text(
            f"❌ Ошибка при генерации отчёта:\n`{str(e)[:200]}`",
            #reply_markup=admin_user_profile_keyboard(target_user_id)
        )
