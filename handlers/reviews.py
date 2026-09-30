from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from database.db import SessionLocal
from database.models import Order, Review, User
from utils.states import ReviewFlow
from config import REVIEWS_CHANNEL_ID, REVIEWS_CHANNEL_USERNAME
from keyboards.inline import back_to_menu_kb, review_rating_kb

router = Router()


def _stars(n: int) -> str:
    return "⭐" * n


async def _safe_delete(bot, chat_id: int, message_id: int):
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass


@router.callback_query(F.data.startswith("review:write:"))
async def review_start(cb: CallbackQuery, state: FSMContext):
    order_id = int(cb.data.split(":")[2])
    user_id = cb.from_user.id

    async with SessionLocal() as s:
        order = await s.get(Order, order_id)
        if not order or order.user_id != user_id or order.status != "approved":
            await cb.answer("Нельзя оставить отзыв к этому заказу", show_alert=True)
            return

        existing = (await s.execute(
            select(Review).where(Review.order_id == order_id)
        )).scalar_one_or_none()
        if existing:
            await cb.answer("Ты уже оставил отзыв к этому заказу 💚", show_alert=True)
            return

    await state.update_data(order_id=order_id)
    await state.set_state(ReviewFlow.rating)

    try:
        await cb.message.edit_text(
            "📝 <b>Оцени свой заказ</b>\n\nПоставь оценку от 1 до 5 звёзд:",
            reply_markup=review_rating_kb(order_id),
            parse_mode="HTML",
        )
    except Exception:
        sent = await cb.message.answer(
            "📝 <b>Оцени свой заказ</b>\n\nПоставь оценку от 1 до 5 звёзд:",
            reply_markup=review_rating_kb(order_id),
            parse_mode="HTML",
        )
        await state.update_data(rating_msg_id=sent.message_id)


@router.callback_query(ReviewFlow.rating, F.data.startswith("review:rate:"))
async def review_rating(cb: CallbackQuery, state: FSMContext):
    _, _, order_id_str, rating_str = cb.data.split(":")
    order_id = int(order_id_str)
    rating = int(rating_str)

    await state.update_data(order_id=order_id, rating=rating)
    await state.set_state(ReviewFlow.text)

    sent = await cb.message.edit_text(
        f"Ты поставил: <b>{rating} {_stars(rating)}</b>\n\n"
        f"Теперь напиши текст отзыва.\n"
        f"Можно отправить просто текст или фото с подписью.\n\n"
        f"Отправь /cancel, чтобы отменить.",
        parse_mode="HTML",
    )
    # сохраняем id сообщения с рейтингом, чтобы удалить после отзыва
    if sent:
        await state.update_data(rating_msg_id=sent.message_id)
    else:
        await state.update_data(rating_msg_id=cb.message.message_id)


@router.message(ReviewFlow.text)
async def review_receive(msg: Message, state: FSMContext):
    # отмена
    if msg.text and msg.text.strip().lower() == "/cancel":
        await _safe_delete(msg.bot, msg.chat.id, msg.message_id)
        data = await state.get_data()
        rating_msg_id = data.get("rating_msg_id")
        if rating_msg_id:
            await _safe_delete(msg.bot, msg.chat.id, rating_msg_id)
        await state.clear()
        await msg.answer("❌ Отзыв отменён.", reply_markup=back_to_menu_kb())
        return

    data = await state.get_data()
    order_id = data.get("order_id")
    rating = data.get("rating", 5)
    rating_msg_id = data.get("rating_msg_id")

    text = None
    photo_id = None
    has_photo = False

    if msg.photo:
        photo_id = msg.photo[-1].file_id
        has_photo = True
        text = msg.caption or "(без текста)"
    elif msg.text:
        text = msg.text
    else:
        # неподходящий тип — удаляем сообщение юзера и просим заново
        await _safe_delete(msg.bot, msg.chat.id, msg.message_id)
        await msg.answer("❌ Можно отправить только текст или фото с подписью.")
        return

    if not text or len(text.strip()) < 2:
        await _safe_delete(msg.bot, msg.chat.id, msg.message_id)
        await msg.answer("❌ Слишком короткий отзыв, напиши что-нибудь по-существу.")
        return

    async with SessionLocal() as s:
        user = await s.get(User, msg.from_user.id)

        existing = (await s.execute(
            select(Review).where(Review.order_id == order_id)
        )).scalar_one_or_none()
        if existing:
            await _safe_delete(msg.bot, msg.chat.id, msg.message_id)
            if rating_msg_id:
                await _safe_delete(msg.bot, msg.chat.id, rating_msg_id)
            await msg.answer(
                "Ты уже оставил отзыв к этому заказу 💚",
                reply_markup=back_to_menu_kb(),
            )
            await state.clear()
            return

        review = Review(
            user_id=msg.from_user.id,
            order_id=order_id,
            rating=rating,
            text=text,
            photo_id=photo_id,
            has_photo=has_photo,
        )
        s.add(review)
        await s.commit()

    # пересылаем в канал ДО удаления сообщения юзера
    try:
        forwarded = await msg.bot.forward_message(
            chat_id=REVIEWS_CHANNEL_ID,
            from_chat_id=msg.chat.id,
            message_id=msg.message_id,
        )

        username = f"@{user.username}" if user.username else f"id{user.id}"
        stars_str = _stars(rating)

        await msg.bot.send_message(
            chat_id=REVIEWS_CHANNEL_ID,
            text=f"✍️ Отзыв от {username}\n{stars_str}",
            reply_to_message_id=forwarded.message_id,
        )
    except Exception as e:
        print("Ошибка публикации отзыва:", e)
        await _safe_delete(msg.bot, msg.chat.id, msg.message_id)
        if rating_msg_id:
            await _safe_delete(msg.bot, msg.chat.id, rating_msg_id)
        await msg.answer(
            "⚠️ Не удалось опубликовать отзыв в канал. Админ уже в курсе.",
            reply_markup=back_to_menu_kb(),
        )
        await state.clear()
        return

    # удаляем сообщение юзера и сообщение с рейтингом
    await _safe_delete(msg.bot, msg.chat.id, msg.message_id)
    if rating_msg_id:
        await _safe_delete(msg.bot, msg.chat.id, rating_msg_id)

    await msg.answer(
        f"🎉 <b>Спасибо за отзыв!</b>\n\n"
        f"Твоя оценка: <b>{rating} {_stars(rating)}</b>\n"
        f"Отзыв опубликован в {REVIEWS_CHANNEL_USERNAME} 💚",
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML",
    )
    await state.clear()
