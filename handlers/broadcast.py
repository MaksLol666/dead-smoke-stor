import asyncio
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from database.db import SessionLocal
from database.models import User
from utils.states import Broadcast
from config import ADMIN_ID

router = Router()


def is_admin(uid: int) -> bool:
    return uid == ADMIN_ID


@router.message(Command("broadcast"))
async def bc_start(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    await msg.answer(
        "📢 <b>Рассылка</b>\n\n"
        "Отправь сообщение, которое нужно разослать всем пользователям.\n"
        "Можно текст, фото с подписью, видео и т.д.\n\n"
        "Для отмены: /cancel",
        parse_mode="HTML"
    )
    await state.set_state(Broadcast.content)


@router.message(Command("cancel"))
async def bc_cancel(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("❌ Отменено.")


@router.message(Broadcast.content)
async def bc_content(msg: Message, state: FSMContext):
    await state.update_data(chat_id=msg.chat.id, message_id=msg.message_id)

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Отправить всем", callback_data="bc:send")
    kb.button(text="❌ Отмена", callback_data="bc:cancel")
    kb.adjust(1)

    async with SessionLocal() as s:
        total = len((await s.execute(select(User))).scalars().all())

    await msg.answer(
        f"📢 Получателей: <b>{total}</b>\n\nПодтверди отправку:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML",
    )
    await state.set_state(Broadcast.confirm)


@router.callback_query(Broadcast.confirm, F.data == "bc:cancel")
async def bc_abort(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("❌ Рассылка отменена.")


@router.callback_query(Broadcast.confirm, F.data == "bc:send")
async def bc_send(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    from_chat = data["chat_id"]
    from_msg = data["message_id"]
    await state.clear()
    await cb.message.edit_text("⏳ Рассылка запущена…")

    async with SessionLocal() as s:
        users = (await s.execute(select(User))).scalars().all()

    ok, fail = 0, 0
    for u in users:
        try:
            await cb.bot.copy_message(
                chat_id=u.id,
                from_chat_id=from_chat,
                message_id=from_msg,
            )
            ok += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail += 1

    await cb.message.edit_text(
        f"✅ Рассылка завершена.\nУспешно: <b>{ok}</b>\nОшибок: <b>{fail}</b>",
        parse_mode="HTML"
)
