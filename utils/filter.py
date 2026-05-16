# utils/filter.py

from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from config import config

class IsOwner(BaseFilter):
    """
    Фильтр: разрешает доступ только владельцу бота (OWNER_ID из config).
    Можно использовать в @router.message(...) или @router.callback_query(...)
    """
    async def __call__( self, event: Message | CallbackQuery) -> bool:
        # Получаем user_id из разных типов событий
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
        else:
            return False
        
        return user_id == config.bot.owner_id

# Экземпляр для удобного импорта
is_owner = IsOwner()

