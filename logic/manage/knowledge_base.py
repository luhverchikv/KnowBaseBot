# logic/manage/knowledge_base.py
import os
import asyncio
from pathlib import Path
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest

# Исправлен путь импорта функций БД
from database.requests import (
    get_user_max_file_size, 
    add_file_to_db, 
    get_user_max_files, 
    get_user_files, 
    get_file_by_id, 
    delete_file_from_db
)

router = Router()
BASE_DIR = Path("database")

# ✅ Разрешённые расширения (только markdown)
ALLOWED_EXTENSIONS = {".md", ".markdown"}

def _physical_delete(path_str: str) -> bool:
    """Удаляет файл физически с диска."""
    path = Path(path_str)
    if path.exists():
        path.unlink()
        return True
    return False

def _get_user_dir(user_id: int) -> Path:
    """Возвращает путь к директории пользователя, создаёт её при необходимости."""
    user_dir = BASE_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir

def get_manage_keyboard() -> InlineKeyboardBuilder:
    """Собирает inline-клавиатуру управления базой."""
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="📥 Загрузить", callback_data="kb_upload"))
    kb.row(InlineKeyboardButton(text="🗑️ Удалить", callback_data="kb_delete"))
    kb.row(InlineKeyboardButton(text="👁️ Просмотреть", callback_data="kb_view"))
    kb.row(InlineKeyboardButton(text="❌ Закрыть", callback_data="close_callback"))
    return kb

async def get_manage_text(user_id: int) -> str:
    """Формирует текст статуса базы знаний (переведено на ORM)."""
    user_files = await get_user_files(user_id)
    files_count = len(user_files)
    return (
        f"📂 <b>Управление базой знаний</b>\n\n"
        f"📄 Загружено файлов: <b>{files_count}</b>\n\n"
        "Выберите действие:"
    )


# ====== Триггер ====
@router.message(F.text == "📂 Управление базой")
async def handle_manage(message: Message):
    text = await get_manage_text(message.from_user.id)
    await message.answer(
        text=text,
        reply_markup=get_manage_keyboard().as_markup(),
        parse_mode="HTML"
    )
    try:
        await message.delete()
    except TelegramBadRequest:
        pass


# ===================== CALLBACK HANDLERS =====================
@router.callback_query(F.data == "kb_upload")
async def cb_upload(call: CallbackQuery):
    await call.answer()
    user_id = call.from_user.id
    max_size_mb = await get_user_max_file_size(user_id)
    await call.message.edit_text(
        "📤 <b>Загрузка файла</b>\n\n"
        "Отправьте файл (markdown).\n"
        f"Максимальный размер: {max_size_mb} МБ.\n"
        "Файл будет сохранён в вашу личную базу знаний.",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "kb_delete")
async def cb_delete_menu(call: CallbackQuery):
    await call.answer()
    user_id = call.from_user.id
    
    # 🔎 Загружаем список файлов из базы данных
    files = await get_user_files(user_id)
    
    if not files:
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="manage_back"))
        await call.message.edit_text(
            "📂 Ваша база знаний пуста. Загрузите файлы через раздел «Загрузить».",
            reply_markup=kb.as_markup()
        )
        return

    kb = InlineKeyboardBuilder()
    for f in files:
        # ✅ Передаем только ID записи в БД вместо имени файла
        kb.row(InlineKeyboardButton(text=f"🗑 {f.filename}", callback_data=f"del_confirm:{f.id}"))
        
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="manage_back"))
    await call.message.edit_text("Выберите файл для удаления:", reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("del_confirm:"))
async def cb_delete_confirm(call: CallbackQuery):
    await call.answer()
    file_id = int(call.data.split(":", 1)[1])
    
    # Получаем имя файла из БД по его ID для вывода в сообщении
    file_data = await get_file_by_id(file_id)
    
    if not file_data:
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="kb_delete"))
        await call.message.edit_text("❌ Файл уже удален или не найден.", reply_markup=kb.as_markup())
        return

    kb = InlineKeyboardBuilder()
    kb.row(
        # ✅ В коллбэк удаления тоже передаем компактный ID
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"del_exec:{file_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="kb_delete")
    )
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="manage_back"))
    
    await call.message.edit_text(
        f"🗑 Вы уверены, что хотите удалить файл <code>{file_data.filename}</code>?",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("del_exec:"))
async def cb_delete_exec(call: CallbackQuery):
    await call.answer()
    file_id = int(call.data.split(":", 1)[1])
    
    # 1. Удаляем запись из базы данных и получаем объект файла
    deleted_file_data = await delete_file_from_db(file_id)
    
    if deleted_file_data:
        # 2. Удаляем файл физически с диска, используя сохраненный в БД путь
        file_deleted = await asyncio.to_thread(_physical_delete, deleted_file_data.file_path)
        
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="kb_delete"))
        
        if file_deleted:
            await call.message.edit_text(
                f"✅ Файл <code>{deleted_file_data.filename}</code> успешно удалён из базы данных и с диска.", 
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
        else:
            await call.message.edit_text(
                f"⚠️ Запись о файле <code>{deleted_file_data.filename}</code> удалена из БД, но сам файл не был найден на диске.", 
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
    else:
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="kb_delete"))
        await call.message.edit_text("❌ Ошибка: файл не найден в базе данных.", reply_markup=kb.as_markup())


@router.callback_query(F.data == "kb_view")
async def cb_view_menu(call: CallbackQuery):
    await call.answer()
    user_id = call.from_user.id
    
    # 🔎 Получаем файлы из базы данных вместо сканирования жесткого диска
    files = await get_user_files(user_id)
    
    if not files:
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="manage_back"))
        await call.message.edit_text(
            "📂 Ваша база знаний пуста.", 
            reply_markup=kb.as_markup()
        )
        return

    kb = InlineKeyboardBuilder()
    for f in files:
        kb.row(InlineKeyboardButton(text=f"👁 {f.filename}", callback_data=f"view_info:{f.id}"))
        
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="manage_back"))
    await call.message.edit_text("📄 Список файлов в вашей базе знаний:", reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("view_info:"))
async def cb_view_info(call: CallbackQuery):
    await call.answer()
    file_id = int(call.data.split(":", 1)[1])
    
    # 🔎 Ищем данные о файле в БД по ID
    file_data = await get_file_by_id(file_id)
    
    if file_data:
        created_str = file_data.created_at.strftime("%d.%m.%Y %H:%M")
        
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="🔙 К списку файлов", callback_data="kb_view"))
        
        await call.message.edit_text(
            f"📄 <b>Имя файла:</b> <code>{file_data.filename}</code>\n"
            f"📝 <b>Описание:</b> {file_data.description}\n"
            f"🕒 <b>Дата добавления:</b> {created_str}",
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )
    else:
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="🔙 К списку файлов", callback_data="kb_view"))
        await call.message.edit_text(
            "❌ Файл не найден в базе данных.", 
            reply_markup=kb.as_markup()
        )


@router.callback_query(F.data == "manage_back")
async def cb_manage_back(call: CallbackQuery):
    await call.answer()
    text = await get_manage_text(call.from_user.id)
    await call.message.edit_text(
        text=text,
        reply_markup=get_manage_keyboard().as_markup(),
        parse_mode="HTML"
    )


# ===================== DOCUMENT HANDLER =====================
@router.message(F.document)
async def handle_document_upload(message: Message):
    doc = message.document
    filename = doc.file_name or "unknown"
    user_id = message.from_user.id
    
    async def safe_delete_message():
        try:
            await message.delete()
        except TelegramBadRequest:
            pass

    # ✅ 1. Проверка расширения файла
    _, ext = os.path.splitext(filename.lower())
    if ext not in ALLOWED_EXTENSIONS:
        await message.answer(
            f"❌ Недопустимый формат файла.\n"
            f"Разрешены только файлы <b>.md</b> (Markdown).\n"
            f"Ваш файл: <code>{filename}</code>",
            parse_mode="HTML"
        )
        await safe_delete_message()
        return
    
    # ✅ 2. Получаем лимит размера из БД напрямую через ORM
    max_size_mb = await get_user_max_file_size(user_id)
    max_size_bytes = max_size_mb * 1024 * 1024

    # Проверка размера
    if doc.file_size and doc.file_size > max_size_bytes:
        await message.answer(
            f"❌ Файл слишком большой.\n"
            f"Ваш лимит: <b>{max_size_mb} МБ</b>.\n"
            f"Размер файла: {doc.file_size / (1024 * 1024):.2f} МБ",
            parse_mode="HTML"
        )
        await safe_delete_message()
        return

    # ✅ 3. Проверка лимита количества файлов (полностью через ORM)
    max_files = await get_user_max_files(user_id)
    user_files = await get_user_files(user_id)
    current_files_count = len(user_files)
    
    if current_files_count >= max_files:
        await message.answer(
            f"❌ Превышен лимит файлов. Максимально разрешено: <b>{max_files}</b>.\n"
            f"Сейчас загружено: <b>{current_files_count}</b>.\n"
            "Удалите ненужные файлы через раздел «🗑️ Удалить», чтобы загрузить новые.",
            parse_mode="HTML"
        )
        await safe_delete_message()
        return

    # 4. ✅ Проверка на существование файла на диске
    user_dir = _get_user_dir(user_id)
    dest_path = user_dir / filename
    
    if dest_path.exists():
        await message.answer(
            f"⚠️ <b>Файл уже существует!</b>\n"
            f"Файл <code>{filename}</code> уже загружен в вашу базу знаний.\n\n"
            f"💡 <b>Что делать:</b>\n"
            f"• Удалите старый файл через раздел «🗑️ Удалить» и загрузите новый\n"
            f"• Или переименуйте файл перед загрузкой",
            parse_mode="HTML"
        )
        await safe_delete_message()
        return

    # 5. Сохранение файла на диск
    await message.bot.download(doc, destination=dest_path)
    
    # 🔥 5.5 Запись информации о файле в базу данных через ORM
    await add_file_to_db(
        user_id=user_id, 
        filename=filename, 
        file_path=str(dest_path)
    )
    
    # 6. Успешный ответ с остатком слотов
    remaining = max_files - current_files_count - 1
    await message.answer(
        f"✅ Файл <code>{filename}</code> успешно сохранён.\n"
        f"📊 Осталось свободных слотов: <b>{remaining}</b> из {max_files}.",
        parse_mode="HTML"
    )
    await safe_delete_message()
