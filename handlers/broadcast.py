import asyncio
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import select
from database.db import SessionLocal
from database.models import User
from utils.states import Broadcast
from config import ADMIN_ID

router = Router()

# 15 сообщений в секунду ≈ 0.067 сек между сообщениями
BROADCAST_DELAY = 0.067
BATCH_SIZE = 50
BATCH_PAUSE = 1.0


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
        total_all = len((await s.execute(select(User))).scalars().all())
        reachable = len((await s.execute(
            select(User).where(User.is_unreachable == False)
        )).scalars().all())

    skipped = total_all - reachable

    await msg.answer(
        f"📢 <b>Получателей:</b>\n"
        f"• Всего в БД: {total_all}\n"
        f"• Доступно: <b>{reachable}</b>\n"
        f"• Пропустим (заблокировали бота): {skipped}\n\n"
        f"⏱ Скорость: ~{int(1 / BROADCAST_DELAY)} сообщ/сек\n"
        f"📦 Батчами по {BATCH_SIZE} с паузой {BATCH_PAUSE} сек\n\n"
        f"Подтверди отправку:",
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
        users = (await s.execute(
            select(User).where(User.is_unreachable == False)
        )).scalars().all()

    total = len(users)
    ok, fail = 0, 0
    newly_unreachable = []

    for i, u in enumerate(users, 1):
        try:
            await cb.bot.copy_message(
                chat_id=u.id,
                from_chat_id=from_chat,
                message_id=from_msg,
            )
            ok += 1

        except TelegramForbiddenError:
            fail += 1
            newly_unreachable.append(u.id)

        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await cb.bot.copy_message(
                    chat_id=u.id,
                    from_chat_id=from_chat,
                    message_id=from_msg,
                )
                ok += 1
            except Exception:
                fail += 1

        except Exception:
            fail += 1

        if i < total:
            await asyncio.sleep(BROADCAST_DELAY)

        if i % BATCH_SIZE == 0 and i < total:
            await asyncio.sleep(BATCH_PAUSE)

        if i % 20 == 0:
            try:
                await cb.message.edit_text(
                    f"⏳ Рассылка: {i}/{total} ({ok} ✅ / {fail} ❌)"
                )
            except Exception:
                pass

    if newly_unreachable:
        async with SessionLocal() as s:
            for uid in newly_unreachable:
                user = await s.get(User, uid)
                if user:
                    user.is_unreachable = True
            await s.commit()

    text = (
        f"✅ <b>Рассылка завершена.</b>\n\n"
        f"📊 Всего: {total}\n"
        f"✅ Успешно: {ok}\n"
        f"❌ Ошибок: {fail}\n"
    )
    if newly_unreachable:
        text += f"\n🚫 Помечено как заблокировавшие: {len(newly_unreachable)}\n"
        text += "<i>Их пропустим в следующих рассылках.</i>"

    try:
        await cb.message.edit_text(text, parse_mode="HTML")
    except Exception:
        pass
