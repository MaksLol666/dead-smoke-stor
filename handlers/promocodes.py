import asyncio
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from database.db import SessionLocal
from database.models import Promocode
from utils.states import PromoEnter
from utils.promo_cache import add_applied, get_promo_prompt_id, set_promo_prompt_id
from keyboards.inline import back_to_menu_kb
from handlers.cart import refresh_cart_message
from config import ADMIN_ID

router = Router()


async def _auto_delete(bot, chat_id: int, message_id: int, delay: int = 0):
    if delay:
        await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass


@router.callback_query(F.data == "promo:enter")
async def promo_enter(cb: CallbackQuery, state: FSMContext):
    sent = await cb.message.answer("Введите промокод:")
    set_promo_prompt_id(cb.from_user.id, sent.message_id)
    await state.set_state(PromoEnter.code)


@router.message(PromoEnter.code)
async def promo_apply(msg: Message, state: FSMContext):
    code = msg.text.strip().upper()
    uid = msg.from_user.id

    # удаляем сообщение юзера с кодом
    try:
        await msg.delete()
    except Exception:
        pass

    # удаляем сообщение бота «Введите промокод:»
    prompt_id = get_promo_prompt_id(uid)
    if prompt_id:
        asyncio.create_task(_auto_delete(msg.bot, msg.chat.id, prompt_id))

    async with SessionLocal() as s:
        promo = await s.get(Promocode, code)

    valid = (
        promo
        and promo.used_count < promo.max_uses
        and (promo.owner_id == uid or promo.owner_id == 0 or uid == ADMIN_ID)
    )
    if not valid:
        notif = await msg.answer("❌ Промокод недействителен или исчерпан.")
        asyncio.create_task(_auto_delete(msg.bot, msg.chat.id, notif.message_id, 3))
        await state.clear()
        return

    if not add_applied(uid, code):
        notif = await msg.answer("Этот промокод уже применён или достигнут лимит (2).")
        asyncio.create_task(_auto_delete(msg.bot, msg.chat.id, notif.message_id, 3))
        await state.clear()
        return

    sign = "₽" if promo.kind == "fixed" else "%"
    notif = await msg.answer(
        f"✅ Промокод <b>{code}</b> на −{int(promo.amount)}{sign} применён.",
        parse_mode="HTML"
    )
    asyncio.create_task(_auto_delete(msg.bot, msg.chat.id, notif.message_id, 2))

    await refresh_cart_message(msg.bot, uid)
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
