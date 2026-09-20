from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select
from database.db import SessionLocal
from database.models import User
from keyboards.inline import back_to_menu_kb

router = Router()


@router.callback_query(F.data == "top:show")
async def show_top(cb: CallbackQuery):
    async with SessionLocal() as s:
        top = (await s.execute(
            select(User).where(User.balance > 0).order_by(User.balance.desc()).limit(3)
        )).scalars().all()

    if not top:
        text = "🏆 Пока никто ничего не купил — стань первым!"
    else:
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, u in enumerate(top):
            name = f"@{u.username}" if u.username else f"id{u.id}"
            lines.append(f"{medals[i]} {name} — <b>{int(u.balance)}₽</b>")
        text = "🏆 <b>Топ-3 покупателей Dead Smoke Store:</b>\n\n" + "\n".join(lines)

    await cb.message.edit_text(text, reply_markup=back_to_menu_kb(), parse_mode="HTML")
