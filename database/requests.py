from database.models import async_session, User, Category, Item
from sqlalchemy import select, update, delete

async def set_user(user_id):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.user_id == user_id))

        if not user:
            session.add(User(user_id=user_id))
            await session.commit()
            return True
        return False