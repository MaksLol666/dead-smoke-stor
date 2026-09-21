from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select, delete
from database.db import SessionLocal
from database.models import CartItem, Product, Order, OrderItem, User
from keyboards.inline import cart_kb, admin_order_kb
from utils.promo_cache import get_applied, clear_applied, set_cart_message, get_cart_message
from utils.pricing import calc_discount
from config import ADMIN_ID

router = Router()


async def render_cart(user_id: int):
    async with SessionLocal() as s:
        rows = (await s.execute(
            select(CartItem, Product).join(Product, CartItem.product_id == Product.id)
            .where(CartItem.user_id == user_id)
        )).all()

    if not rows:
        return None

    applied = get_applied(user_id)
    percent, fixed = await calc_discount(applied)

    subtotal = sum(p.price for _, p in rows)
    after_percent = subtotal * (1 - percent / 100)
    final = max(after_percent - fixed, 0)

    return rows, subtotal, final, percent, fixed, applied


def _render_cart_text(rows, subtotal, final, percent, fixed):
    lines = [f"• {p.brand} — {p.flavor} — {int(p.price)}₽" for _, p in rows]
    text = "🛒 <b>Корзина:</b>\n" + "\n".join(lines)
    text += f"\n\nПодытог: {int(subtotal)}₽"
    if percent:
        text += f"\n🎟 Скидка {int(percent)}%: −{int(subtotal * percent / 100)}₽"
    if fixed:
        text += f"\n🎟 Промокоды: −{int(fixed)}₽"
    text += f"\n\n<b>К оплате: {int(final)}₽</b>"
    return text


async def refresh_cart_message(bot, user_id: int):
    """Перерисовывает сохранённое сообщение корзины."""
    stored = get_cart_message(user_id)
    if not stored:
        return
    chat_id, message_id = stored

    res = await render_cart(user_id)
    if not res:
        try:
            await bot.edit_message_text(
                "🛒 Корзина пуста.",
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=cart_kb(False),
            )
        except Exception:
            pass
        return

    rows, subtotal, final, percent, fixed, applied = res
    text = _render_cart_text(rows, subtotal, final, percent, fixed)
    try:
        await bot.edit_message_text(
            text,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=cart_kb(True),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data == "cart:view")
async def view_cart(cb: CallbackQuery):
    set_cart_message(cb.from_user.id, cb.message.chat.id, cb.message.message_id)
    res = await render_cart(cb.from_user.id)
    if not res:
        await cb.message.edit_text("🛒 Корзина пуста.", reply_markup=cart_kb(False))
        return

    rows, subtotal, final, percent, fixed, applied = res
    text = _render_cart_text(rows, subtotal, final, percent, fixed)
    await cb.message.edit_text(text, reply_markup=cart_kb(True), parse_mode="HTML")


@router.callback_query(F.data == "cart:clear")
async def clear_cart(cb: CallbackQuery):
    async with SessionLocal() as s:
        await s.execute(delete(CartItem).where(CartItem.user_id == cb.from_user.id))
        await s.commit()
    clear_applied(cb.from_user.id)
    await cb.message.edit_text("🗑 Корзина очищена.", reply_markup=cart_kb(False))


@router.callback_query(F.data == "cart:checkout")
async def checkout(cb: CallbackQuery):
    user_id = cb.from_user.id
    res = await render_cart(user_id)
    if not res:
        await cb.answer("Корзина пуста", show_alert=True)
        return

    rows, subtotal, final, percent, fixed, applied = res

    async with SessionLocal() as s:
        order = Order(
            user_id=user_id,
            total=final,
            status="pending",
            promo_codes=",".join(applied) if applied else None,
        )
        s.add(order)
        await s.flush()

        for ci, p in rows:
            s.add(OrderItem(order_id=order.id, product_id=p.id, price=p.price))
            p.in_stock = False
            await s.delete(ci)

        user = await s.get(User, user_id)
        await s.commit()

    clear_applied(user_id)

    lines = "\n".join(f"• {p.brand} — {p.flavor} — {int(p.price)}₽" for _, p in rows)
    text = f"🆕 <b>Новый заказ №{order.id}</b>\n"
    text += f"От: @{user.username or user_id} (<code>{user_id}</code>)\n\n{lines}\n"
    if percent:
        text += f"\n🎟 Скидка {int(percent)}%: −{int(subtotal * percent / 100)}₽"
    if fixed:
        text += f"\n🎟 Промо: −{int(fixed)}₽"
    text += f"\n\n<b>К оплате: {int(final)}₽</b>"

    try:
        await cb.bot.send_message(ADMIN_ID, text, reply_markup=admin_order_kb(order.id), parse_mode="HTML")
    except Exception as e:
        print("Ошибка отправки админу:", e)

    await cb.message.edit_text(
        f"✅ Заказ №{order.id} отправлен администратору.\nК оплате: <b>{int(final)}₽</b>\nОжидайте подтверждения.",
        reply_markup=cart_kb(False),
        parse_mode="HTML",
    )
