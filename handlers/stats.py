from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select, func
from datetime import datetime, timedelta
from database.db import SessionLocal
from database.models import User, Order, OrderItem, Product
from config import ADMIN_ID

router = Router()


def is_admin(uid: int) -> bool:
    return uid == ADMIN_ID


@router.message(Command("stats"))
async def stats(msg: Message):
    if not is_admin(msg.from_user.id):
        return

    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)

    async with SessionLocal() as s:
        total_users = (await s.execute(select(func.count(User.id)))).scalar() or 0

        total_orders = (await s.execute(
            select(func.count(Order.id)).where(Order.status == "approved")
        )).scalar() or 0

        total_revenue = (await s.execute(
            select(func.coalesce(func.sum(Order.total), 0)).where(Order.status == "approved")
        )).scalar() or 0

        pending = (await s.execute(
            select(func.count(Order.id)).where(Order.status == "pending")
        )).scalar() or 0

        revenue_day = (await s.execute(
            select(func.coalesce(func.sum(Order.total), 0))
            .where(Order.status == "approved", Order.created_at >= day_ago)
        )).scalar() or 0

        orders_day = (await s.execute(
            select(func.count(Order.id))
            .where(Order.status == "approved", Order.created_at >= day_ago)
        )).scalar() or 0

        revenue_week = (await s.execute(
            select(func.coalesce(func.sum(Order.total), 0))
            .where(Order.status == "approved", Order.created_at >= week_ago)
        )).scalar() or 0

        orders_week = (await s.execute(
            select(func.count(Order.id))
            .where(Order.status == "approved", Order.created_at >= week_ago)
        )).scalar() or 0

        avg_check = (total_revenue / total_orders) if total_orders else 0

        top_products = (await s.execute(
            select(OrderItem.product_id, func.count(OrderItem.id).label("cnt"))
            .group_by(OrderItem.product_id)
            .order_by(func.count(OrderItem.id).desc())
            .limit(3)
        )).all()

        top_lines = []
        for pid, cnt in top_products:
            p = await s.get(Product, pid)
            if p:
                top_lines.append(f"• {p.brand} — {p.flavor}: {cnt} шт.")
        if not top_lines:
            top_lines.append("• Пока нет продаж")

    text = (
        f"📊 <b>Статистика Dead Smoke Store</b>\n\n"
        f"👥 Пользователей: <b>{total_users}</b>\n"
        f"⏳ Заказов в ожидании: <b>{pending}</b>\n\n"
        f"💵 <b>Выручка:</b>\n"
        f"• Всего: <b>{int(total_revenue)}₽</b> ({total_orders} заказов)\n"
        f"• За сутки: <b>{int(revenue_day)}₽</b> ({orders_day})\n"
        f"• За неделю: <b>{int(revenue_week)}₽</b> ({orders_week})\n"
        f"• Средний чек: <b>{int(avg_check)}₽</b>\n\n"
        f"🏆 <b>Топ-3 товара:</b>\n" + "\n".join(top_lines)
    )
    await msg.answer(text, parse_mode="HTML")
