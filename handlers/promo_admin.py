from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from database.db import SessionLocal
from database.models import Promocode
from utils.promo import gen_promo
from utils.states import PromoCreate
from config import ADMIN_ID

router = Router()


def is_admin(uid: int) -> bool:
    return uid == ADMIN_ID


@router.message(Command("newpromo"))
async def promo_start(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    kb = InlineKeyboardBuilder()
    kb.button(text="💵 Фиксированная сумма (₽)", callback_data="newpromo:fixed")
    kb.button(text="📉 Процент скидки (%)", callback_data="newpromo:percent")
    kb.adjust(1)
    await msg.answer(
        "🎫 <b>Создание промокода</b>\n\nВыбери тип:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(PromoCreate.kind)


@router.callback_query(PromoCreate.kind, F.data.startswith("newpromo:"))
async def promo_kind(cb: CallbackQuery, state: FSMContext):
    kind = cb.data.split(":")[1]
    await state.update_data(kind=kind)
    if kind == "fixed":
        await cb.message.edit_text("Введи сумму скидки (₽):")
    else:
        await cb.message.edit_text("Введи процент скидки (например, 10):")
    await state.set_state(PromoCreate.amount)


@router.message(PromoCreate.amount)
async def promo_amount(msg: Message, state: FSMContext):
    try:
        val = float(msg.text.replace(",", ".").replace("%", "").replace("₽", "").strip())
    except ValueError:
        await msg.answer("Введи число.")
        return
    if val <= 0:
        await msg.answer("Число должно быть больше нуля.")
        return
    data = await state.get_data()
    if data["kind"] == "percent" and val > 100:
        await msg.answer("Процент не может быть больше 100.")
        return
    await state.update_data(amount=val)
    await msg.answer("Сколько активаций у промокода? (число, например 1 или 100):")
    await state.set_state(PromoCreate.uses)


@router.message(PromoCreate.uses)
async def promo_uses(msg: Message, state: FSMContext):
    try:
        uses = int(msg.text.strip())
    except ValueError:
        await msg.answer("Введи целое число.")
        return
    if uses < 1:
        await msg.answer("Минимум 1 активация.")
        return
    await state.update_data(max_uses=uses)
    await msg.answer(
        "Введи свой код (латиница + цифры, до 16 символов)\n"
        "или отправь <code>auto</code> — сгенерирую сам.",
        parse_mode="HTML"
    )
    await state.set_state(PromoCreate.custom_code)


@router.message(PromoCreate.custom_code)
async def promo_code(msg: Message, state: FSMContext):
    raw = msg.text.strip().upper()
    data = await state.get_data()

    async with SessionLocal() as s:
        if raw == "AUTO":
            code = gen_promo()
            while await s.get(Promocode, code):
                code = gen_promo()
        else:
            code = raw
            if not code.isalnum() or len(code) > 16:
                await msg.answer("❌ Код должен быть буквенно-цифровой, до 16 символов.")
                return
            if await s.get(Promocode, code):
                await msg.answer("❌ Такой код уже существует.")
                return

        s.add(Promocode(
            code=code,
            owner_id=0,
            kind=data["kind"],
            amount=data["amount"],
            max_uses=data["max_uses"],
            used_count=0,
            created_by="admin",
        ))
        await s.commit()

    sign = "₽" if data["kind"] == "fixed" else "%"
    await msg.answer(
        f"✅ Промокод создан!\n\n"
        f"🎫 Код: <code>{code}</code>\n"
        f"💰 Скидка: <b>{int(data['amount'])}{sign}</b>\n"
        f"🔢 Активаций: <b>{data['max_uses']}</b>\n\n"
        f"Работает для всех пользователей.",
        parse_mode="HTML"
    )
    await state.clear()


@router.message(Command("allpromos"))
async def all_promos(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    async with SessionLocal() as s:
        promos = (await s.execute(
            select(Promocode).where(Promocode.used == False).order_by(Promocode.created_by)
        )).scalars().all()
    if not promos:
        await msg.answer("Промокодов нет.")
        return

    by_src = {"admin": [], "system": [], "ref": []}
    for p in promos:
        sign = "₽" if p.kind == "fixed" else "%"
        uses_left = p.max_uses - p.used_count
        by_src.setdefault(p.created_by, []).append(
            f"<code>{p.code}</code> — {int(p.amount)}{sign} "
            f"(осталось: {uses_left}/{p.max_uses}, owner: {p.owner_id})"
        )

    text = "🎫 <b>Активные промокоды:</b>\n"
    for src, name in [("admin", "🔧 Ручные"), ("ref", "🎁 Реферальные"), ("system", "⚙️ Прочие")]:
        if by_src.get(src):
            text += f"\n<b>{name}:</b>\n" + "\n".join(by_src[src])
    await msg.answer(text, parse_mode="HTML")
