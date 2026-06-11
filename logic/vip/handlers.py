# logic/vip/handlers.py

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.filters import Command
from datetime import datetime, timedelta


from database.requests import (
    get_user_subscription_status,
    upgrade_to_premium,
    get_daily_pool_generations,
    get_generation_limit
)
from logic.vip.keyboards import vip_menu_keyboard, vip_confirm_keyboard
from utils.logger import logger

router = Router()

# Цены в Stars
VIP_PRICES = {
    30: 150,   # 30 дней = 150 Stars
    90: 400    # 90 дней = 400 Stars
}

@router.message(Command("vip"))
async def cmd_vip(message: Message):
    """Команда /vip - показать VIP-меню"""
    user_id = message.from_user.id
    sub_status = await get_user_subscription_status(user_id)
    
    if sub_status["status"] == "premium":
        until_str = sub_status["until"].strftime("%d.%m.%Y") if sub_status["until"] else "—"
        text = (
            f"💎 <b>VIP-статус активен!</b>\n\n"
            f"✅ Подписка действует до: <b>{until_str}</b>\n"
            f"🚀 Лимит генераций: <b>10 в сутки</b>\n\n"
            f"Спасибо за поддержку проекта! 🙏"
        )
    else:
        current_gens = await get_daily_pool_generations(user_id)
        limit = await get_generation_limit(user_id)
        
        text = (
            f"⭐ <b>VIP-подписка</b>\n\n"
            f"📊 Ваш текущий статус: <b>Free</b>\n"
            f"🎲 Генераций сегодня: <b>{current_gens}/{limit}</b>\n\n"
            f"💎 <b>Преимущества Premium:</b>\n"
            f"• 🚀 10 генераций пулов в сутки (вместо 2)\n"
            f"• ⚡ Приоритетная обработка запросов\n"
            f"• 🎁 Поддержка развития бота\n\n"
            f"Выберите тариф ниже:"
        )
    
    await message.answer(text, reply_markup=vip_menu_keyboard(), parse_mode="HTML")

@router.callback_query(F.data == "vip_menu")
async def show_vip_menu(call: CallbackQuery):
    """Показать VIP-меню"""
    user_id = call.from_user.id
    sub_status = await get_user_subscription_status(user_id)
    
    if sub_status["status"] == "premium":
        until_str = sub_status["until"].strftime("%d.%m.%Y") if sub_status["until"] else "—"
        text = (
            f"💎 <b>VIP-статус активен!</b>\n\n"
            f"✅ Подписка действует до: <b>{until_str}</b>\n"
            f"🚀 Лимит генераций: <b>10 в сутки</b>"
        )
    else:
        current_gens = await get_daily_pool_generations(user_id)
        limit = await get_generation_limit(user_id)
        
        text = (
            f"⭐ <b>VIP-подписка</b>\n\n"
            f"📊 Ваш статус: <b>Free</b>\n"
            f"🎲 Генераций сегодня: <b>{current_gens}/{limit}</b>\n\n"
            f"💎 Выберите тариф:"
        )
    
    await call.message.edit_text(text, reply_markup=vip_menu_keyboard(), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data.startswith("vip_buy_"))
async def show_vip_offer(call: CallbackQuery, bot: Bot):
    """Показать предложение о покупке"""
    await call.answer()
    
    try:
        days = int(call.data.split("_")[2])
        price = VIP_PRICES.get(days)
        
        if not price:
            await call.message.answer("❌ Неверный тариф")
            return
        
        text = (
            f"💎 <b>Подписка VIP на {days} дней</b>\n\n"
            f"💰 Стоимость: <b>{price} Stars</b>\n"
            f"🚀 Лимит генераций: <b>10 в сутки</b>\n"
            f"⏰ Действует до: <b>{(datetime.now() + timedelta(days=days)).strftime('%d.%m.%Y')}</b>\n\n"
            f"Нажмите кнопку ниже для оплаты:"
        )
        
        # Создаём invoice
        prices = [LabeledPrice(label=f"VIP {days} дней", amount=price * 100)]  # Цена в копейках (1 Star = 100 копеек)
        
        await bot.send_invoice(
            chat_id=call.from_user.id,
            title=f"VIP-подписка на {days} дней",
            description=f"Расширенный лимит генераций вопросов (10 в сутки) на {days} дней",
            payload=f"vip_{days}_{call.from_user.id}",
            provider_token="",  # Пустой токен для Telegram Stars
            currency="XTR",     # XTR = Telegram Stars
            prices=prices
        )
        
    except Exception as e:
        logger.error(f"Error creating invoice: {e}")
        await call.message.answer("❌ Ошибка создания счёта. Попробуйте позже.")

@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    """Обработка pre-checkout запроса"""
    try:
        # Здесь можно добавить дополнительную проверку
        await pre_checkout_query.answer(ok=True)
    except Exception as e:
        logger.error(f"Pre-checkout error: {e}")
        await pre_checkout_query.answer(ok=False, error_message="Ошибка обработки платежа")

@router.message(F.successful_payment)
async def process_successful_payment(message: Message):
    """Обработка успешного платежа"""
    try:
        payment = message.successful_payment
        payload = payment.payload
        
        # Парсим payload: vip_{days}_{user_id}
        parts = payload.split("_")
        if len(parts) != 3 or parts[0] != "vip":
            logger.error(f"Invalid payment payload: {payload}")
            await message.answer("❌ Ошибка обработки платежа")
            return
        
        days = int(parts[1])
        user_id = int(parts[2])
        
        # Активируем подписку
        await upgrade_to_premium(user_id, days)
        
        logger.info(f"✅ User {user_id} upgraded to premium for {days} days")
        
        await message.answer(
            f"🎉 <b>Оплата прошла успешно!</b>\n\n"
            f"💎 Ваш VIP-статус активирован на <b>{days} дней</b>\n"
            f"🚀 Теперь у вас <b>10 генераций</b> пулов вопросов в сутки\n\n"
            f"Спасибо за поддержку! 🙏",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.exception(f"Payment processing error: {e}")
        await message.answer("❌ Ошибка активации подписки. Свяжитесь с поддержкой.")

@router.callback_query(F.data == "vip_cancel")
async def cancel_vip_purchase(call: CallbackQuery):
    """Отмена покупки"""
    await call.answer("Покупка отменена")
    await call.message.delete()
