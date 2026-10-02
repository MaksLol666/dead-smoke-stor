import asyncio
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, delete, func
from database.db import SessionLocal
from database.models import User, Order, Promocode, CartItem
from utils.states import UserManage
from keyboards.inline import user_manage_kb
from config import ADMIN_ID

router = Router()


def is_admin(uid: int) -> bool:
    return uid == ADMIN_ID


async def _safe_delete(bot, chat_id: int, message_id: int):
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass


async def _auto_delete(bot, chat_id: int, message_id: int, delay: int = 0):
    if delay:
        await asyncio.sleep(delay)
    await _safe_delete(bot, chat_id, message_id)


async def _build_user_card(user: User) -> str:
    async with SessionLocal() as s:
        orders_count = (await s.execute(
            select(func.count(Order.id)).where(
                Order.user_id == user.id,
                Order.status == "approved",
            )
        )).scalar() or 0

        promos_count = (await s.execute(
            select(func.count(Promocode.code)).where(
                Promocode.owner_id == user.id,
                Promocode.used == False,
            )
        )).scalar() or 0

    name = f"@{user.username}" if user.username else "(нет username)"
    status = "🚫 <b>ЗАБАНЕН</b>" if user.is_banned else "✅ активен"

    text = (
        f"👤 <b>Информация о пользователе</b>\n\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"📛 Username: {name}\n"
        f"💰 Потрачено: <b>{int(user.balance)}₽</b>\n"
        f"🛍 Покупок: <b>{orders_count}</b>\n"
        f"👥 Рефералов (купивших): <b>{user.referrals_count}</b>\n"
        f"🎟 Активных промо: <b>{promos_count}</b>\n"
        f"📊 Статус: {status}"
    )
    return text


# ======================== /user ========================
@router.message(Command("user"))
async def user_command(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    await _safe_delete(msg.bot, msg.chat.id, msg.message_id)

    sent = await msg.answer("👤 Введи <b>@username</b> или <b>ID</b> пользователя:", parse_mode="HTML")
    await state.update_data(prompt_msg_id=sent.message_id)
    await state.set_state(UserManage.waiting_query)


@router.message(UserManage.waiting_query, Command("cancel"))
async def user_cancel(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    await _safe_delete(msg.bot, msg.chat.id, msg.message_id)
    data = await state.get_data()
    prompt_id = data.get("prompt_msg_id")
    if prompt_id:
        await _safe_delete(msg.bot, msg.chat.id, prompt_id)
    await state.clear()
    sent = await msg.answer("❌ Отменено.")
    asyncio.create_task(_auto_delete(msg.bot, msg.chat.id, sent.message_id, 3))


@router.message(UserManage.waiting_query)
async def user_query(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return

    query = msg.text.strip() if msg.text else ""
    await _safe_delete(msg.bot, msg.chat.id, msg.message_id)

    data = await state.get_data()
    prompt_id = data.get("prompt_msg_id")
    if prompt_id:
        await _safe_delete(msg.bot, msg.chat.id, prompt_id)

    async with SessionLocal() as s:
        if query.startswith("@"):
            username_clean = query[1:]
            user = (await s.execute(
                select(User).where(User.username == username_clean)
            )).scalar_one_or_none()
        else:
            try:
                uid = int(query)
            except ValueError:
                sent = await msg.answer("❌ Некорректный формат. Введи @username или ID.")
                asyncio.create_task(_auto_delete(msg.bot, msg.chat.id, sent.message_id, 3))
                return
            user = await s.get(User, uid)

    if not user:
        await state.clear()
        sent = await msg.answer("❌ Пользователь не найден.")
        asyncio.create_task(_auto_delete(msg.bot, msg.chat.id, sent.message_id, 3))
        return

    await state.clear()

    text = await _build_user_card(user)
    await msg.answer(
        text,
        reply_markup=user_manage_kb(user.id, user.is_banned),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "user:cancel")
async def user_card_cancel(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await state.clear()
    try:
        await cb.message.delete()
    except Exception:
        pass


@router.callback_query(F.data.startswith("user:ban:"))
async def user_ban(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    uid = int(cb.data.split(":")[2])

    async with SessionLocal() as s:
        user = await s.get(User, uid)
        if not user:
            await cb.answer("Пользователь не найден.", show_alert=True)
            return
        user.is_banned = True
        await s.commit()

    text = await _build_user_card(user)
    try:
        await cb.message.edit_text(
            text + "\n\n✅ <b>Пользователь забанен.</b>",
            reply_markup=user_manage_kb(user.id, user.is_banned),
            parse_mode="HTML",
        )
    except Exception:
        pass

    try:
        await cb.bot.send_message(user.id, "❌ Ты заблокирован в этом боте.")
    except Exception:
        pass


@router.callback_query(F.data.startswith("user:unban:"))
async def user_unban(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    uid = int(cb.data.split(":")[2])

    async with SessionLocal() as s:
        user = await s.get(User, uid)
        if not user:
            await cb.answer("Пользователь не найден.", show_alert=True)
            return
        user.is_banned = False
        await s.commit()

    text = await _build_user_card(user)
    try:
        await cb.message.edit_text(
            text + "\n\n✅ <b>Пользователь разбанен.</b>",
            reply_markup=user_manage_kb(user.id, user.is_banned),
            parse_mode="HTML",
        )
    except Exception:
        pass

    try:
        await cb.bot.send_message(user.id, "✅ Ты снова можешь пользоваться ботом.")
    except Exception:
        pass


@router.callback_query(F.data.startswith("user:reset:"))
async def user_reset(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    uid = int(cb.data.split(":")[2])

    async with SessionLocal() as s:
        user = await s.get(User, uid)
        if not user:
            await cb.answer("Пользователь не найден.", show_alert=True)
            return

        user.balance = 0
        user.referrals_count = 0
        user.next_bonus_at = 10
        user.first_purchase_done = False

        await s.execute(delete(Promocode).where(Promocode.owner_id == uid))

        await s.commit()

    text = await _build_user_card(user)
    try:
        await cb.message.edit_text(
            text + "\n\n✅ <b>Статистика обнулена, промокоды удалены.</b>\n"
                   "<i>(история заказов сохранена)</i>",
            reply_markup=user_manage_kb(user.id, user.is_banned),
            parse_mode="HTML",
        )
    except Exception:
        pass


# ======================== /wipeusers ========================
@router.message(Command("wipeusers"))
async def wipe_users_start(msg: Message):
    if not is_admin(msg.from_user.id):
        return

    await _safe_delete(msg.bot, msg.chat.id, msg.message_id)

    async with SessionLocal() as s:
        total = (await s.execute(select(func.count(User.id)))).scalar() or 0

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, удалить всех", callback_data="wipe:confirm")
    kb.button(text="❌ Отмена", callback_data="wipe:cancel")
    kb.adjust(1)

    sent = await msg.answer(
        f"⚠️ <b>Массовое удаление пользователей</b>\n\n"
        f"Сейчас в БД: <b>{total}</b> юзеров\n"
        f"Будет удалено: <b>{total - 1}</b> (все, кроме тебя)\n\n"
        f"<b>Что НЕ трогается:</b>\n"
        f"• 📦 Товары и категории\n"
        f"• 📜 История заказов\n"
        f"• ⭐ Отзывы\n\n"
        f"<b>Что удалится:</b>\n"
        f"• 👥 Все юзеры кроме тебя\n"
        f"• 🛒 Их корзины\n"
        f"• 🎟 Промокоды удалённых юзеров\n\n"
        f"Топ-10 и Топ реферов станут пустыми (это норма).",
        reply_markup=kb.as_markup(),
        parse_mode="HTML",
    )
    asyncio.create_task(_auto_delete(msg.bot, msg.chat.id, sent.message_id, 60))


@router.callback_query(F.data == "wipe:cancel")
async def wipe_cancel(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    try:
        await cb.message.delete()
    except Exception:
        pass
    sent = await cb.message.answer("❌ Отменено.")
    asyncio.create_task(_auto_delete(cb.bot, cb.message.chat.id, sent.message_id, 3))


@router.callback_query(F.data == "wipe:confirm")
async def wipe_confirm(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return

    try:
        await cb.message.delete()
    except Exception:
        pass

    await cb.message.answer("⏳ Удаляю юзеров…")

    async with SessionLocal() as s:
        total_before = (await s.execute(select(func.count(User.id)))).scalar() or 0

        await s.execute(delete(CartItem).where(CartItem.user_id != ADMIN_ID))

        await s.execute(
            delete(Promocode).where(
                Promocode.owner_id != ADMIN_ID,
                Promocode.owner_id != 0,
            )
        )

        await s.execute(delete(User).where(User.id != ADMIN_ID))

        await s.commit()

        total_after = (await s.execute(select(func.count(User.id)))).scalar() or 0

    removed = total_before - total_after

    sent = await cb.message.answer(
        f"✅ <b>Готово!</b>\n\n"
        f"🗑 Удалено юзеров: <b>{removed}</b>\n"
        f"👤 Осталось: <b>{total_after}</b> (ты)\n\n"
        f"Товары, категории, заказы, отзывы — на месте.",
        parse_mode="HTML",
    )
    asyncio.create_task(_auto_delete(cb.bot, cb.message.chat.id, sent.message_id, 10))
