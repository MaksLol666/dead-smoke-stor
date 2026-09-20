from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from database.db import SessionLocal
from database.models import Promocode
from utils.states import PromoEnter
from utils.promo_cache import add_applied
from keyboards.inline import back_to_menu_kb
from config import ADMIN_ID

router = Router()


@router.callback_query(F.data == "promo:enter")
async def promo_enter(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("Введите промокод:")
    await state.set_state(PromoEnter.code)


@router.message(PromoEnter.code)
async def promo_apply(msg: Message, state: FSMContext):
    code = msg.text.strip().upper()
    uid = msg.from_user.id

    async with SessionLocal() as s:
        promo = await s.get(Promocode, code)

    valid = (
        promo and not promo.used
        and (promo.owner_id == uid or promo.owner_id == 0 or uid == ADMIN_ID)
    )
    if not valid:
        await msg.answer("❌ Промокод недействителен.")
        await state.clear()
        return

    if not add_applied(uid, code):
        await msg.answer("Этот промокод уже применён или достигнут лимит (2).")
        await state.clear()
        return

    sign = "₽" if promo.kind == "fixed" else "%"
    await msg.answer(
        f"✅ Промокод <b>{code}</b> на −{int(promo.amount)}{sign} применён.",
        parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(F.data == "promo:mine")
async def my_promos(cb: CallbackQuery):
    uid = cb.from_user.id
    async with SessionLocal() as s:
        promos = (await s.execute(
            select(Promocode).where(
                Promocode.owner_id == uid,
                Promocode.used == False
            )
        )).scalars().all()

    if not promos:
        text = "🎟 У вас пока нет активных промокодов."
    else:
        lines = []
        for p in promos:
            sign = "₽" if p.kind == "fixed" else "%"
            lines.append(f"• <code>{p.code}</code> — {int(p.amount)}{sign}")
        text = "🎟 <b>Ваши активные промокоды:</b>\n\n" + "\n".join(lines)

    await cb.message.edit_text(text, reply_markup=back_to_menu_kb(), parse_mode="HTML")
