# logic/vip/handlers.py

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery, SuccessfulPayment
from aiogram.filters import Command
from datetime import datetime, timedelta
from typing import Optional

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

# Минимальная ожидаемая сумма платежа (в копейках)
MIN_PAYMENT_AMOUNT = 100  # 1 Star = 100 копеек


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ВАЛИДАЦИИ
# =============================================================================

def validate_payment_payload(payload: str) -> Optional[tuple[int, int]]:
    """
    Валидирует payload платежа.

    Args:
        payload: Строка payload в формате "vip_{days}_{user_id}"

    Returns:
        tuple(days, user_id) если валидно, None если нет
    """
    try:
        parts = payload.split("_")
        if len(parts) != 3 or parts[0] != "vip":
            logger.warning(f"Invalid payload format: {payload}")
            return None

        days = int(parts[1])
        user_id = int(parts[2])

        # Проверяем, что days в допустимых значениях
        if days not in VIP_PRICES:
            logger.warning(f"Invalid subscription days: {days}")
            return None

        return days, user_id
    except (ValueError, IndexError) as e:
        logger.warning(f"Failed to parse payload: {payload}, error: {e}")
        return None


def validate_successful_payment(payment: SuccessfulPayment, expected_user_id: int) -> tuple[bool, str]:
    """
    Комплексная валидация успешного платежа.

    Args:
        payment: Объект SuccessfulPayment
        expected_user_id: Ожидаемый ID пользователя из payload

    Returns:
        tuple(is_valid, error_message)
    """
    # 1. Проверяем telegram_payment_charge_id (обязателен для Stars)
    if not payment.telegram_payment_charge_id:
        logger.error(f"Missing telegram_payment_charge_id for user {expected_user_id}")
        return False, "Отсутствует ID платежа Telegram"

    # 2. Проверяем, что сумма не нулевая
    if payment.total_amount <= 0:
        logger.error(f"Invalid total_amount: {payment.total_amount}")
        return False, "Некорректная сумма платежа"

    # 3. Проверяем валюту (должна быть XTR для Stars)
    if payment.currency != "XTR":
        logger.warning(f"Unexpected currency: {payment.currency}")
        return False, "Неподдерживаемая валюта"

    # 4. Проверяем минимальную сумму (защита от фейковых платежей)
    if payment.total_amount < MIN_PAYMENT_AMOUNT:
        logger.error(f"Payment amount too low: {payment.total_amount}")
        return False, "Сумма платежа слишком мала"

    return True, ""


async def extend_subscription(user_id: int, additional_days: int) -> datetime:
    """
    Расширяет подписку пользователя.
    Если подписка ещё активна — добавляет дни к текущей.
    Если истекла — активирует заново.

    Returns:
        Новая дата окончания подписки
    """
    from database.requests import get_user_subscription_status

    current_status = await get_user_subscription_status(user_id)
    now = datetime.now()

    if current_status["status"] == "premium" and current_status["until"]:
        # Продлеваем от текущей даты окончания (или от now если ещё не истекла)
        current_end = current_status["until"]
        if current_end > now:
            # Подписка ещё активна — продлеваем от неё
            new_until = current_end + timedelta(days=additional_days)
        else:
            # Подписка истекла — активируем от now
            new_until = now + timedelta(days=additional_days)
    else:
        # Нет активной подписки — активируем с нуля
        new_until = now + timedelta(days=additional_days)

    # Обновляем в БД
    await upgrade_to_premium(user_id, additional_days)

    return new_until


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
        # Валидируем payload перед подтверждением
        payload = pre_checkout_query.invoice_payload
        parsed = validate_payment_payload(payload)

        if not parsed:
            logger.warning(f"Invalid pre-checkout payload: {payload}")
            await pre_checkout_query.answer(
                ok=False,
                error_message="Некорректные данные заказа. Попробуйте снова."
            )
            return

        days, user_id = parsed

        # Проверяем, что пользователь не покупает сам себе (защита от CSRF-подобных атак)
        if pre_checkout_query.from_user.id != user_id:
            logger.warning(
                f"User mismatch in pre-checkout: from={pre_checkout_query.from_user.id}, payload={user_id}"
            )
            await pre_checkout_query.answer(
                ok=False,
                error_message="Ошибка идентификации пользователя."
            )
            return

        await pre_checkout_query.answer(ok=True)

    except Exception as e:
        logger.error(f"Pre-checkout error: {e}")
        await pre_checkout_query.answer(ok=False, error_message="Ошибка обработки платежа")


@router.message(F.successful_payment)
async def process_successful_payment(message: Message):
    """Обработка успешного платежа с полной валидацией"""
    payment = message.successful_payment
    user_id = message.from_user.id

    try:
        # 1. Валидация payload
        parsed = validate_payment_payload(payment.payload)
        if not parsed:
            logger.error(f"Invalid payment payload: {payment.payload}")
            await message.answer("❌ Ошибка обработки платежа: некорректные данные.")
            return

        days, payload_user_id = parsed

        # 2. Проверка соответствия user_id
        if user_id != payload_user_id:
            logger.error(
                f"🚨 POSSIBLE FRAUD: User ID mismatch! "
                f"message.from_user.id={user_id}, payload.user_id={payload_user_id}, "
                f"telegram_charge_id={payment.telegram_payment_charge_id}"
            )
            await message.answer("❌ Ошибка безопасности. Свяжитесь с поддержкой.")
            return

        # 3. Валидация самого платежа
        is_valid, error_msg = validate_successful_payment(payment, user_id)
        if not is_valid:
            logger.error(f"Payment validation failed for user {user_id}: {error_msg}")
            await message.answer(f"❌ Ошибка валидации платежа: {error_msg}")
            return

        # 4. Расширяем подписку (с учётом уже активной)
        new_until = await extend_subscription(user_id, days)

        # 5. Полное логирование платежа
        logger.info(
            f"💰 PAYMENT SUCCESS: user_id={user_id}, "
            f"days={days}, "
            f"amount={payment.total_amount} {payment.currency}, "
            f"telegram_charge_id={payment.telegram_payment_charge_id}, "
            f"new_subscription_until={new_until.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        # 6. Формируем сообщение пользователю
        was_active = await get_user_subscription_status(user_id)
        renewal_text = (
            "♻️ Ваша подписка продлена!"
            if was_active["status"] == "premium" and was_active["until"] and was_active["until"] > datetime.now()
            else "🎉 Поздравляем с приобретением VIP!"
        )

        await message.answer(
            f"{renewal_text}\n\n"
            f"💎 <b>VIP-статус активирован!</b>\n\n"
            f"📅 Подписка действует до: <b>{new_until.strftime('%d.%m.%Y')}</b>\n"
            f"🚀 Лимит генераций: <b>10 в сутки</b>\n"
            f"💰 Оплачено: <b>{payment.total_amount // 100} Stars</b>\n\n"
            f"Спасибо за поддержку проекта! 🙏",
            parse_mode="HTML"
        )

    except Exception as e:
        logger.exception(f"Payment processing error for user {user_id}: {e}")
        await message.answer(
            "❌ Произошла ошибка при активации подписки. "
            "Пожалуйста, свяжитесь с поддержкой и укажите ваш Telegram ID."
        )

@router.callback_query(F.data == "vip_cancel")
async def cancel_vip_purchase(call: CallbackQuery):
    """Отмена покупки"""
    await call.answer("Покупка отменена")
    await call.message.delete()
