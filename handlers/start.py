import asyncio
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy import select
from database.db import SessionLocal
from database.models import User
from keyboards.inline import main_menu_kb
from utils.dice import random_dice
from config import REFERRAL_MILESTONE, REFERRAL_MILESTONE_DISCOUNT

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    tg_id = message.from_user.id
    username = message.from_user.username or message.from_user.full_name

    args = message.text.split(maxsplit=1)
    referrer_id = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer_id = int(args[1][4:])
            if referrer_id == tg_id:
                referrer_id = None
        except ValueError:
            pass

    async with SessionLocal() as s:
        user = await s.get(User, tg_id)
        if not user:
            user = User(id=tg_id, username=username, referrer_id=referrer_id)
            s.add(user)
            await s.commit()

            if referrer_id:
                try:
                    await message.bot.send_message(
                        referrer_id,
                        f"🔔 По вашей ссылке зашёл новый пользователь: @{username or tg_id}\n"
                        f"💡 Реферал засчитается после его первой покупки."
                    )
                except Exception:
                    pass

        bot_info = await message.bot.me()
        ref_link = f"https://t.me/{bot_info.username}?start=ref_{tg_id}"

    dice_msg = await message.answer_dice(emoji=random_dice())
    await asyncio.sleep(3.5)
    try:
        await dice_msg.delete()
    except Exception:
        pass

    text = (
        f"💨 <b>Dead Smoke Store</b> приветствует тебя!\n\n"
        f"🔗 Твоя реферальная ссылка:\n<code>{ref_link}</code>\n\n"
        f"🎁 За каждого приглашённого — 15% от его первой покупки\n"
        f"🏆 За каждые {REFERRAL_MILESTONE} <b>купивших</b> друзей — промокод на −{int(REFERRAL_MILESTONE_DISCOUNT)}%"
    )
    await message.answer(text, reply_markup=main_menu_kb(), parse_mode="HTML")


@router.callback_query(F.data == "menu:main")
async def back_to_menu(cb):
    await cb.message.edit_text(
        "💨 <b>Dead Smoke Store</b>\n\nГлавное меню:",
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
                             )
