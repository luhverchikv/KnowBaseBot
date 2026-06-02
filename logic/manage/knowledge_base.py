# logic/manage/knowledge_base.py
import os
import asyncio
from pathlib import Path
from database import get_user_max_file_size, add_file_to_db, get_user_max_files
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()
BASE_DIR = Path("database")

# ✅ Разрешённые расширения (только markdown)
ALLOWED_EXTENSIONS = {".md", ".markdown"}


def _get_user_dir(user_id: int) -> Path:
    """Возвращает путь к директории пользователя, создаёт её при необходимости."""
    user_dir = BASE_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def _list_files(user_id: int) -> list[str]:
    """Возвращает отсортированный список .md файлов пользователя."""
    user_dir = _get_user_dir(user_id)
    # ✅ Фильтруем только разрешённые расширения
    return sorted([
        f.name for f in user_dir.iterdir() 
        if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS
    ])
    
    
def _delete_file(user_id: int, filename: str) -> bool:
    """Удаляет файл. Возвращает True при успехе."""
    file_path = _get_user_dir(user_id) / filename
    if file_path.exists():
        file_path.unlink()
        return True
    return False

def get_manage_keyboard() -> InlineKeyboardBuilder:
    """Собирает inline-клавиатуру управления базой."""
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="📥 Загрузить", callback_data="kb_upload"))
    kb.row(InlineKeyboardButton(text="🗑️ Удалить", callback_data="kb_delete"))
    kb.row(InlineKeyboardButton(text="👁️ Просмотреть", callback_data="kb_view"))
    kb.row(InlineKeyboardButton(text="❌ Закрыть", callback_data="close_callback"))
    return kb

def get_manage_text(user_id: int) -> str:
    """Формирует текст статуса базы знаний."""
    files_count = len(_list_files(user_id))
    return (
        f"📂 <b>Управление базой знаний</b>\n\n"
        f"📄 Загружено файлов: <b>{files_count}</b>\n\n"
        "Выберите действие:"
    )


# ======Тригер====
@router.message(F.text == "📂 Управление базой")
async def handle_manage(message: Message):
    await message.answer(
        text=get_manage_text(message.from_user.id),
        reply_markup=get_manage_keyboard().as_markup(),
        parse_mode="HTML"
    )
    await message.delete()


# ===================== CALLBACK HANDLERS =====================
@router.callback_query(F.data == "kb_upload")
async def cb_upload(call: CallbackQuery):
    await call.answer()
    user_id = call.message.from_user.id
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
    files = await asyncio.to_thread(_list_files, call.from_user.id)
    if not files:
        await call.message.edit_text("📂 Ваша база знаний пуста. Загрузите файлы через раздел «Загрузить».")
        return

    kb = InlineKeyboardBuilder()
    for f in files:
        kb.row(InlineKeyboardButton(text=f"🗑 {f}", callback_data=f"del_confirm:{f}"))
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="manage_back"))
    await call.message.edit_text("Выберите файл для удаления:", reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("del_confirm:"))
async def cb_delete_confirm(call: CallbackQuery):
    await call.answer()
    filename = call.data.split(":", 1)[1]
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"del_exec:{filename}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="kb_delete")
    )
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="manage_back"))
    await call.message.edit_text(
        f"🗑 Вы уверены, что хотите удалить файл <code>{filename}</code>?",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("del_exec:"))
async def cb_delete_exec(call: CallbackQuery):
    await call.answer()
    filename = call.data.split(":", 1)[1]
    success = await asyncio.to_thread(_delete_file, call.from_user.id, filename)
    if success:
        await call.message.edit_text(f"✅ Файл <code>{filename}</code> успешно удалён.", parse_mode="HTML")
    else:
        await call.message.edit_text("❌ Ошибка: файл не найден.")

@router.callback_query(F.data == "kb_view")
async def cb_view_menu(call: CallbackQuery):
    await call.answer()
    files = await asyncio.to_thread(_list_files, call.from_user.id)
    if not files:
        await call.message.answer("📂 Ваша база знаний пуста.")
        return

    kb = InlineKeyboardBuilder()
    for f in files:
        kb.row(InlineKeyboardButton(text=f"👁 {f}", callback_data=f"view_info:{f}"))
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="manage_back"))
    await call.message.edit_text("📄 Список файлов в вашей базе знаний:", reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("view_info:"))
async def cb_view_info(call: CallbackQuery):
    await call.answer()
    filename = call.data.split(":", 1)[1]
    file_path = _get_user_dir(call.from_user.id) / filename
    if file_path.exists():
        size_mb = file_path.stat().st_size / (1024 * 1024)
        await call.message.edit_text(
            f"📄 <b>{filename}</b>\n"
            f"📦 Размер: {size_mb:.2f} МБ\n"
            f"🕒 Последнее изменение: {file_path.stat().st_mtime}",
            parse_mode="HTML"
        )
    else:
        await call.message.edit_text("❌ Файл не найден.")

@router.callback_query(F.data == "manage_back")
async def cb_manage_back(call: CallbackQuery):
    await call.answer()
    await call.message.edit_text(
        text=get_manage_text(call.from_user.id),
        reply_markup=get_manage_keyboard().as_markup(),
        parse_mode="HTML"
    )


# ===================== DOCUMENT HANDLER =====================
@router.message(F.document)
async def handle_document_upload(message: Message):
    doc = message.document
    filename = doc.file_name or "unknown"
    user_id = message.from_user.id
    
    # Заранее подготовим безопасное удаление сообщения пользователя в конце или при ошибке
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

    # ✅ 3. Получаем лимит количества файлов из БД напрямую через ORM
    max_files = await get_user_max_files(user_id)
    current_files = await asyncio.to_thread(_list_files, user_id) # Оставляем в потоке, т.к. это работа с диском os.listdir
    
    if len(current_files) >= max_files:
        await message.answer(
            f"❌ Превышен лимит файлов. Максимально разрешено: <b>{max_files}</b>.\n"
            f"Сейчас загружено: <b>{len(current_files)}</b>.\n"
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
    remaining = max_files - len(current_files) - 1
    await message.answer(
        f"✅ Файл <code>{filename}</code> успешно сохранён.\n"
        f"📊 Осталось свободных слотов: <b>{remaining}</b> из {max_files}.",
        parse_mode="HTML"
    )
    await safe_delete_message()
