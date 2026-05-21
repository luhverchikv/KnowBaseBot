# voice_engine/handler.py

import os
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from mongo import add_blood_pressure_entry, get_last_bp_timestamp #, get_user_topic_id
from logic.bp_limits import check_bp_interval
from loguru import logger
from datetime import datetime
from menu.keyboard import menu_kb


from .converter import ogg_to_wav
from .recognizer import recognize_text_from_wav
from .parser import extract_values
from .format_texts import format_values
from .normalizer import normalize_medical_terms
from .validator import validate_pressure, validate_pulse, ValidationStatus
from .bp_save_kb import build_bp_keyboard

voice_router = Router()
voice_logger = logger.bind(module="voice")


@voice_router.message(F.voice)
async def process_voice(message: Message):
    user_id = message.from_user.id
    # 🔊 ПРОВЕРКА ДЛИТЕЛЬНОСТИ ГОЛОСОВОГО СООБЩЕНИЯ
    if message.voice.duration > 10:  # ограничение по длине 10 секунд
        await message.answer(
            "⚠️ <b>Голосовое сообщение слишком длинное</b>\n"
            "Пожалуйста, отправляйте сообщения не длиннее 10 секунд.\n"
            "Это помогает системе работать стабильно и быстро обрабатывать ваши данные.",
            parse_mode="HTML"
        )
        await message.delete()
        voice_logger.bind(
            user_id=user_id,
            event_type="voice_rejected"
        ).warning(f"Voice message too long: {message.voice.duration}s")
        return  # ❌ Прерываем обработку
    
    # 👉 проверка последнего измерения
    last_time = await get_last_bp_timestamp(user_id)
    allowed, minutes_ago = check_bp_interval(last_time)

    if not allowed:
        await message.answer(
            f"⏱ Вы недавно вносили артериальное давление.\n\n"
            f"Последнее измерение было {minutes_ago} мин назад.\n"
            f"Повторное измерение можно внести через "
            f"{45 - minutes_ago} мин.",
        )
        return  # ❌ прерываем выполнение
        
    """Обрабатывает голосовое сообщение: распознаёт текст и данные."""

    file = await message.bot.get_file(message.voice.file_id)
    ogg_path = f"temp_{message.from_user.id}.ogg"
    wav_path = f"temp_{message.from_user.id}.wav"

    await message.bot.download_file(file.file_path, destination=ogg_path)
    await ogg_to_wav(ogg_path, wav_path)

    # Распознавание
    raw_text = recognize_text_from_wav(wav_path)
    text = normalize_medical_terms(raw_text)
    
    # Логирование
    voice_logger.bind(
        user_id=user_id,
        event_type="voice_input"
    ).info(f"VOICE TEXT: {text}")
    
    values = extract_values(text)
    
    pressure_status = None
    pressure_notes = []
    pulse_status = None
    pulse_notes = []

    if values.get("systolic") and values.get("diastolic"):
        pressure_status, pressure_notes = validate_pressure(
            values["systolic"],
            values["diastolic"]
        )

    if values.get("pulse"):
        pulse_status, pulse_notes = validate_pulse(values["pulse"])

    can_save = True

    if pressure_status == ValidationStatus.INVALID:
        can_save = False

    if pulse_status == ValidationStatus.INVALID:
        can_save = False
        
    # Удаляем временные файлы
    for p in (ogg_path, wav_path):
        if os.path.exists(p):
            os.remove(p)

    # Формирование сообщения
    msg = (
        f"🔎 <b>Распознан текст:</b>\n{text}\n\n"
    )
    
    formatted_values = format_values(
    values,
    pressure_status=pressure_status,
    pressure_notes=pressure_notes,
    pulse_status=pulse_status,
    pulse_notes=pulse_notes,
    )

    if formatted_values:
        msg += f"\n{formatted_values}"
    else:
        msg += "\n⚠️ <i>Не удалось извлечь числовые значения</i>"
    
    bp_keyboard = build_bp_keyboard(
    systolic=values["systolic"],
    diastolic=values["diastolic"],
    pulse=values["pulse"],
    arrhythmic=values["arrhythmic"],
    can_save=can_save
    )

    
    await message.answer(
    msg,
    reply_markup=bp_keyboard,
    parse_mode="HTML")
    
    await message.delete()
    
    
@voice_router.callback_query(F.data.startswith("bp|"))
async def handle_bp_callback(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    if callback.data == "bp|cancel":
        await callback.message.edit_text("❌ Сохранение отменено")
        return

    data = dict(
        part.split("=")
        for part in callback.data.split("|")[1:]
    )

    systolic = int(data["s"])
    diastolic = int(data["d"])
    pulse_value = data["p"]
    if pulse_value != "None":
        pulse = int(pulse_value)
    else:
        pulse = None
    arrhythmic = bool(int(data["a"]))
    
    # 🔐 ПОВТОРНАЯ ВАЛИДАЦИЯ (ОБЯЗАТЕЛЬНО)
    pressure_status, _ = validate_pressure(systolic, diastolic)
    if pressure_status == ValidationStatus.INVALID:
        await callback.message.edit_text(
            "❌ Давление недопустимо и не может быть сохранено"
        )
        return

    if pulse is not None:
        pulse_status, _ = validate_pulse(pulse)
        if pulse_status == ValidationStatus.INVALID:
            await callback.message.edit_text(
                "❌ Пульс недопустим и не может быть сохранён"
            )
            return
            
            
    # 🕒 время сохранения (UTC, как в БД)
    timestamp = datetime.utcnow()
    formatted_time = timestamp.strftime("%d.%m.%Y %H:%M")
    # 👉 запись в БД
    success = await add_blood_pressure_entry(
        user_id=user_id,
        systolic=systolic,
        diastolic=diastolic,
        pulse=pulse,
        arrhythmic=arrhythmic,
    )

    if success:
        # 🧾 Формируем текст подтверждения
        text = (
            f"✅ Показатели успешно сохранены\n\n"
            f"📅 <b>{formatted_time}</b>\n"
            f"⏱️ Давление: <b>{systolic}/{diastolic}</b> мм рт. ст."
        )

        if pulse is not None:
            text += f"\n❤️ Пульс: <b>{pulse}</b> уд/мин"

        if arrhythmic:
            text += "\n⚠️ Отмечена аритмия"
        
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="HTML",
                reply_markup=menu_kb()
            )
            
        except TelegramBadRequest as e:
            if "message thread not found" in str(e):
                await callback.message.answer(
                    "⚠️ Топик удалён. Восстановите его через /start"
                )
            else:
                raise
                
        await callback.message.delete()
        #await callback.message.edit_text(text, parse_mode="HTML")
    else:
        await callback.message.edit_text("❌ Не удалось сохранить данные")
        
