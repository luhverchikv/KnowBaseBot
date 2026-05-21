# voice_engine/handler.py

import os
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from datetime import datetime
from .converter import ogg_to_wav
from .recognizer import recognize_text_from_wav


router = Router()


@voice_router.message(F.voice)
async def process_voice(message: Message):
    user_id = message.from_user.id
    # 🔊 ПРОВЕРКА ДЛИТЕЛЬНОСТИ ГОЛОСОВОГО СООБЩЕНИЯ
    if message.voice.duration > 60:  # ограничение по длине 60 секунд
        await message.answer(
            "⚠️ <b>Голосовое сообщение слишком длинное</b>\n"
            "Пожалуйста, отправляйте сообщения не длиннее 60 секунд.\n"
            "Это помогает системе работать стабильно и быстро обрабатывать ваши данные.",
            parse_mode="HTML"
        )
        await message.delete()
        return  # ❌ Прерываем обработку
    
    
    
    """Обрабатывает голосовое сообщение: распознаёт текст."""

    file = await message.bot.get_file(message.voice.file_id)
    ogg_path = f"temp_{message.from_user.id}.ogg"
    wav_path = f"temp_{message.from_user.id}.wav"

    await message.bot.download_file(file.file_path, destination=ogg_path)
    await ogg_to_wav(ogg_path, wav_path)

    # Распознавание
    raw_text = recognize_text_from_wav(wav_path)
        
    # Удаляем временные файлы
    for p in (ogg_path, wav_path):
        if os.path.exists(p):
            os.remove(p)
    
    await message.answer(
    text=raw_text,
    parse_mode="HTML")
    await message.delete()
