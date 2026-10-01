from typing import Any, Awaitable, Callable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from database.db import SessionLocal
from database.models import User
from config import ADMIN_ID


class BanCheckMiddleware(BaseMiddleware):
    """
    Проверяет, забанен ли юзер. Если да — отвечает и блокирует апдейт.
    Админ не банится никогда.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # получаем user_id из события
        user = None
        if isinstance(event, (Message, CallbackQuery)):
            user = event.from_user

        if user is None:
            return await handler(event, data)

        # админ не банится
        if user.id == ADMIN_ID:
            return await handler(event, data)

        # проверяем бан в БД
        async with SessionLocal() as s:
            db_user = await s.get(User, user.id)

        if db_user and db_user.is_banned:
            if isinstance(event, Message):
                try:
                    await event.answer("❌ Ты заблокирован в этом боте.")
                except Exception:
                    pass
            elif isinstance(event, CallbackQuery):
                try:
                    await event.answer("❌ Ты заблокирован в этом боте.", show_alert=True)
                except Exception:
                    pass
            return  # не пропускаем дальше

        return await handler(event, data)
