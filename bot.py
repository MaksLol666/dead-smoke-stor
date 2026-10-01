import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from sqlalchemy import select, text

from config import BOT_TOKEN, CATEGORIES
from database.db import init_db, SessionLocal, engine
from database.models import Category
from middlewares.ban_check import BanCheckMiddleware

from handlers import (
    start, catalog, cart, admin, promocodes,
    top, profile, history, broadcast, promo_admin, stats, reviews, user_admin
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("dead_smoke")


async def run_migrations():
    """Аккуратно добавляет новые столбцы в существующие таблицы."""
    migrations = [
        ("orders", "delivery_type", "TEXT DEFAULT 'pickup'"),
        ("orders", "delivery_name", "TEXT"),
        ("orders", "delivery_phone", "TEXT"),
        ("orders", "delivery_address", "TEXT"),
        ("users", "is_banned", "INTEGER DEFAULT 0"),
    ]
    async with engine.begin() as conn:
        for table, column, coltype in migrations:
            try:
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}"))
                log.info("Migration: added %s.%s", table, column)
            except Exception:
                pass


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

    # регистрируем middleware для проверки бана
    dp.message.middleware(BanCheckMiddleware())
    dp.callback_query.middleware(BanCheckMiddleware())

    dp.include_router(admin.router)
    dp.include_router(user_admin.router)
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
    dp.include_router(reviews.router)

    await init_db()
    await run_migrations()
    await seed_categories()

    log.info("💨 Dead Smoke Store запущен, начинаю polling…")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Остановлено вручную")
