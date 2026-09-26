from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select
from database.db import SessionLocal
from database.models import User
from keyboards.inline import back_to_menu_kb

router = Router()


def _format_top(users: list[User], value_fn, empty_text: str, title: str) -> str:
    if not users:
        return empty_text

    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, u in enumerate(users):
        name = f"@{u.username}" if u.username else f"id{u.id}"
        prefix = medals[i] if i < 3 else f"{i + 1}."
        lines.append(f"{prefix} {name} — <b>{value_fn(u)}</b>")
    return title + "\n\n" + "\n".join(lines)


@router.callback_query(F.data == "top:show")
async def show_top_buyers(cb: CallbackQuery):
    """Топ-10 покупателей по сумме потраченного."""
    async with SessionLocal() as s:
        top = (await s.execute(
            select(User).where(User.balance > 0)
            .order_by(User.balance.desc())
            .limit(10)
        )).scalars().all()

    text = _format_top(
        top,
        value_fn=lambda u: f"{int(u.balance)}₽",
        empty_text="🏆 Пока никто ничего не купил — стань первым!",
        title="🏆 <b>Топ-10 покупателей Dead Smoke Store:</b>",
    )
    await cb.message.edit_text(text, reply_markup=back_to_menu_kb(), parse_mode="HTML")


@router.callback_query(F.data == "topref:show")
async def show_top_referrers(cb: CallbackQuery):
    """Топ-10 реферов — считаются только рефералы, которые КУПИЛИ."""
    async with SessionLocal() as s:
        top = (await s.execute(
            select(User).where(User.referrals_count > 0)
            .order_by(User.referrals_count.desc())
            .limit(10)
        )).scalars().all()

    text = _format_top(
        top,
        value_fn=lambda u: f"{u.referrals_count} чел.",
        empty_text="👥 Пока никто не привёл купивших друзей — будь первым!",
        title="👥 <b>Топ-10 реферов Dead Smoke Store:</b>\n<i>(считаются только те рефералы, которые купили)</i>",
    )
    await cb.message.edit_text(text, reply_markup=back_to_menu_kb(), parse_mode="HTML")
