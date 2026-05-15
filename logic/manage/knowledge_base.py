# logic/manage/knowledge_base.py

# logic/manage/knowledge_base.py
import os
import asyncio
from pathlib import Path
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()
BASE_DIR = Path("database")

def _get_user_dir(user_id: int) -> Path:
    """Возвращает путь к директории пользователя, создаёт её при необходимости."""
    user_dir = BASE_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir

def _list_files(user_id: int) -> list[str]:
    """Возвращает отсортированный список файлов пользователя."""
    return sorted([f.name for f in _get_user_dir(user_id).iterdir() if f.is_file()])

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
@router.message(F.text == "Управление базой")
async def handle_manage(message: Message):
    await message.answer(
        text=get_manage_text(message.from_user.id),
        reply_markup=get_manage_keyboard().as_markup(),
        parse_mode="HTML"
    )


# ===================== CALLBACK HANDLERS =====================
@router.callback_query(F.data == "kb_upload")
async def cb_upload(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        "📤 <b>Загрузка файла</b>\n\n"
        "Отправьте файл (PDF, TXT, DOCX, CSV, MD).\n"
        "Максимальный размер: 2 МБ.\n"
        "Файл будет сохранён в вашу личную базу знаний.",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "kb_delete")
async def cb_delete_menu(call: CallbackQuery):
    await call.answer()
    files = await asyncio.to_thread(_list_files, call.from_user.id)
    if not files:
        await call.message.answer("📂 Ваша база знаний пуста. Загрузите файлы через раздел «Загрузить».")
        return

    kb = InlineKeyboardBuilder()
    for f in files:
        kb.row(InlineKeyboardButton(text=f"🗑 {f}", callback_data=f"del_confirm:{f}"))
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="manage_back"))
    await call.message.answer("Выберите файл для удаления:", reply_markup=kb.as_markup())

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
    await call.message.answer(
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
        await call.message.answer(f"✅ Файл <code>{filename}</code> успешно удалён.", parse_mode="HTML")
    else:
        await call.message.answer("❌ Ошибка: файл не найден.")

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
    await call.message.answer("📄 Список файлов в вашей базе знаний:", reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("view_info:"))
async def cb_view_info(call: CallbackQuery):
    await call.answer()
    filename = call.data.split(":", 1)[1]
    file_path = _get_user_dir(call.from_user.id) / filename
    if file_path.exists():
        size_mb = file_path.stat().st_size / (1024 * 1024)
        await call.message.answer(
            f"📄 <b>{filename}</b>\n"
            f"📦 Размер: {size_mb:.2f} МБ\n"
            f"🕒 Последнее изменение: {file_path.stat().st_mtime}",
            parse_mode="HTML"
        )
    else:
        await call.message.answer("❌ Файл не найден.")

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
    # Лимит 20 МБ (Telegram API обычно не пропускает больше)
    if doc.file_size and doc.file_size > 2 * 1024 * 1024:
        await message.answer("❌ Файл слишком большой. Максимальный размер: 2 МБ.")
        return

    # Если файл с таким именем уже есть, добавим уникальный суффикс
    dest_path = _get_user_dir(message.from_user.id) / doc.file_name
    if dest_path.exists():
        name, ext = os.path.splitext(doc.file_name)
        dest_path = _get_user_dir(message.from_user.id) / f"{name}_{dest_path.stat().st_mtime:.0f}{ext}"

    await doc.download(destination_file=dest_path)
    await message.answer(
        f"✅ Файл <code>{dest_path.name}</code> успешно сохранён в базу знаний.",
        parse_mode="HTML"
    )

