from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select, func
from database.db import SessionLocal
from database.models import User, Order, Promocode
from keyboards.inline import profile_kb

router = Router()


@router.callback_query(F.data == "profile:show")
async def show_profile(cb: CallbackQuery):
    uid = cb.from_user.id
    async with SessionLocal() as s:
        user = await s.get(User, uid)
        if not user:
            await cb.answer("Сначала /start", show_alert=True)
            return

        orders_count = (await s.execute(
            select(func.count(Order.id)).where(
                Order.user_id == uid, Order.status == "approved"
            )
        )).scalar() or 0

        promos = (await s.execute(
            select(Promocode).where(Promocode.owner_id == uid, Promocode.used == False)
        )).scalars().all()
        fixed_sum = sum(p.amount for p in promos if p.kind == "fixed")
        percent_sum = sum(p.amount for p in promos if p.kind == "percent")

        invited_raw = (await s.execute(
            select(func.count(User.id)).where(User.referrer_id == uid)
        )).scalar() or 0

        bot_info = await cb.bot.me()
        ref_link = f"https://t.me/{bot_info.username}?start=ref_{uid}"

    left = user.next_bonus_at - user.referrals_count
    name = f"@{user.username}" if user.username else f"id{uid}"

    text = (
        f"👤 <b>Мой профиль</b>\n\n"
        f"🆔 {name}\n"
        f"💰 Потрачено: <b>{int(user.balance)}₽</b>\n"
        f"🛍 Покупок: <b>{orders_count}</b>\n"
        f"👥 Зашло по ссылке: {invited_raw}\n"
        f"✅ Из них купили: <b>{user.referrals_count}</b> (до бонуса ещё {left})\n"
        f"🎟 Промо: <b>{len(promos)}</b> — суммовых на {int(fixed_sum)}₽, процентных на {int(percent_sum)}%\n\n"
        f"🔗 Твоя реф-ссылка:\n<code>{ref_link}</code>"
    )
    await cb.message.edit_text(text, reply_markup=profile_kb(ref_link), parse_mode="HTML")
