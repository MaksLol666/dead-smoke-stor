import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from sqlalchemy import select

from config import BOT_TOKEN, CATEGORIES
from database.db import init_db, SessionLocal
from database.models import Category

from handlers import (
    start, catalog, cart, admin, promocodes,
    top, profile, history, broadcast, promo_admin, stats
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("dead_smoke")


async def seed_categories():
    async with SessionLocal() as s:
        existing = (await s.execute(select(Category))).scalars().all()
        if existing:
            return
        for name in CATEGORIES:
            s.add(Category(name=name))
        await s.commit()
        log.info("Категории созданы: %s", ", ".join(CATEGORIES))


async def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Порядок важен: admin первым (ловит callback'и, которые могут конфликтовать с другими)
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(catalog.router)
    dp.include_router(cart.router)
    dp.include_router(promocodes.router)
    dp.include_router(top.router)
    dp.include_router(profile.router)
    dp.include_router(history.router)
    dp.include_router(broadcast.router)
    dp.include_router(promo_admin.router)
    dp.include_router(stats.router)

    await init_db()
    await seed_categories()

    log.info("💨 Dead Smoke Store запущен, начинаю polling…")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Остановлено вручную")
