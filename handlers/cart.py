from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, delete
from database.db import SessionLocal
from database.models import CartItem, Product, Order, OrderItem, User
from keyboards.inline import cart_kb, admin_order_kb, delivery_choice_kb
from utils.promo_cache import get_applied, clear_applied, set_cart_message, get_cart_message
from utils.pricing import calc_discount
from utils.states import Checkout
from config import ADMIN_ID, DELIVERY_PRICE

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


def _render_cart_text(rows, subtotal, final, percent, fixed, delivery_price=0):
    lines = [f"• {p.brand} — {p.flavor} — {int(p.price)}₽" for _, p in rows]
    text = "🛒 <b>Корзина:</b>\n" + "\n".join(lines)
    text += f"\n\nПодытог: {int(subtotal)}₽"
    if percent:
        text += f"\n🎟 Скидка {int(percent)}%: −{int(subtotal * percent / 100)}₽"
    if fixed:
        text += f"\n🎟 Промокоды: −{int(fixed)}₽"
    if delivery_price:
        text += f"\n🚚 Доставка СДЭК: +{int(delivery_price)}₽"
    total_with_delivery = final + delivery_price
    text += f"\n\n<b>К оплате: {int(total_with_delivery)}₽</b>"
    return text


async def refresh_cart_message(bot, user_id: int):
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


# ============== CHECKOUT — шаг 1: выбор доставки ==============
@router.callback_query(F.data == "cart:checkout")
async def checkout_start(cb: CallbackQuery, state: FSMContext):
    res = await render_cart(cb.from_user.id)
    if not res:
        await cb.answer("Корзина пуста", show_alert=True)
        return

    await state.set_state(Checkout.delivery)
    await cb.message.answer(
        "🚚 <b>Выбери способ получения:</b>\n\n"
        f"🏠 Самовывоз — бесплатно\n"
        f"🚚 СДЭК — +{DELIVERY_PRICE}₽ (доставка до ПВЗ)",
        reply_markup=delivery_choice_kb(),
        parse_mode="HTML",
    )


# ============== САМОВЫВОЗ — сразу оформляем ==============
@router.callback_query(Checkout.delivery, F.data == "delivery:pickup")
async def checkout_pickup(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await _finalize_order(
        bot=cb.bot,
        message=cb.message,
        user_id=cb.from_user.id,
        delivery_type="pickup",
        delivery_name=None,
        delivery_phone=None,
        delivery_address=None,
        delivery_price=0,
        editing=False,
    )


# ============== СДЭК — FSM-цепочка ==============
@router.callback_query(Checkout.delivery, F.data == "delivery:cdek")
async def checkout_cdek(cb: CallbackQuery, state: FSMContext):
    await state.update_data(delivery_type="cdek", delivery_price=DELIVERY_PRICE)
    await state.set_state(Checkout.name)
    await cb.message.edit_text(
        "🚚 <b>Оформление СДЭК</b>\n\n"
        "Введи <b>ФИО получателя</b>\n"
        "<i>(как в личном кабинете СДЭК — чтобы ты мог отслеживать заказ в приложении)</i>",
        parse_mode="HTML",
    )


@router.message(Checkout.name)
async def checkout_name(msg: Message, state: FSMContext):
    name = msg.text.strip()
    if len(name) < 3:
        await msg.answer("❌ Слишком короткое ФИО. Введи полное ФИО:")
        return
    await state.update_data(delivery_name=name)
    await state.set_state(Checkout.phone)
    await msg.answer(
        "📱 Введи <b>номер телефона</b> получателя:\n"
        "<i>(например, +7 999 123-45-67)</i>",
        parse_mode="HTML",
    )


@router.message(Checkout.phone)
async def checkout_phone(msg: Message, state: FSMContext):
    phone = msg.text.strip()
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) < 10:
        await msg.answer("❌ Некорректный номер. Введи ещё раз:")
        return
    await state.update_data(delivery_phone=phone)
    await state.set_state(Checkout.city)
    await msg.answer("🏙 Введи <b>город</b>:", parse_mode="HTML")


@router.message(Checkout.city)
async def checkout_city(msg: Message, state: FSMContext):
    city = msg.text.strip()
    if len(city) < 2:
        await msg.answer("❌ Слишком короткое название. Введи город:")
        return
    await state.update_data(delivery_city=city)
    await state.set_state(Checkout.address)
    await msg.answer(
        "📍 Введи <b>точный адрес ПВЗ</b> и, если хочешь, ссылку на Яндекс.Карты.\n\n"
        "<i>Например: г. Москва, ул. Ленина 15, ПВЗ СДЭК (https://yandex.ru/maps/...)</i>",
        parse_mode="HTML",
    )


@router.message(Checkout.address)
async def checkout_address(msg: Message, state: FSMContext):
    address = msg.text.strip()
    if len(address) < 5:
        await msg.answer("❌ Слишком короткий адрес. Введи ещё раз:")
        return
    data = await state.get_data()
    full_address = f"{data.get('delivery_city', '')}, {address}"

    await state.clear()
    await _finalize_order(
        bot=msg.bot,
        message=msg,
        user_id=msg.from_user.id,
        delivery_type="cdek",
        delivery_name=data.get("delivery_name"),
        delivery_phone=data.get("delivery_phone"),
        delivery_address=full_address,
        delivery_price=DELIVERY_PRICE,
        editing=False,
    )


# ============== Финальное оформление ==============
async def _finalize_order(
    bot, message, user_id: int,
    delivery_type: str,
    delivery_name, delivery_phone, delivery_address,
    delivery_price: int,
    editing: bool,
):
    res = await render_cart(user_id)
    if not res:
        await message.answer("Корзина пуста.")
        return

    rows, subtotal, final, percent, fixed, applied = res
    total_with_delivery = final + delivery_price

    async with SessionLocal() as s:
        order = Order(
            user_id=user_id,
            total=total_with_delivery,
            status="pending",
            promo_codes=",".join(applied) if applied else None,
            delivery_type=delivery_type,
            delivery_name=delivery_name,
            delivery_phone=delivery_phone,
            delivery_address=delivery_address,
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

    # уведомление админу
    lines = "\n".join(f"• {p.brand} — {p.flavor} — {int(p.price)}₽" for _, p in rows)
    text = f"🆕 <b>Новый заказ №{order.id}</b>\n"
    text += f"От: @{user.username or user_id} (<code>{user_id}</code>)\n\n{lines}\n"

    if percent:
        text += f"\n🎟 Скидка {int(percent)}%: −{int(subtotal * percent / 100)}₽"
    if fixed:
        text += f"\n🎟 Промо: −{int(fixed)}₽"

    if delivery_type == "cdek":
        text += f"\n\n🚚 <b>СДЭК (+{DELIVERY_PRICE}₽)</b>"
        text += f"\n👤 {delivery_name}"
        text += f"\n📱 {delivery_phone}"
        text += f"\n📍 {delivery_address}"
    else:
        text += f"\n\n🏠 <b>Самовывоз</b>"

    text += f"\n\n<b>К оплате: {int(total_with_delivery)}₽</b>"

    try:
        await bot.send_message(ADMIN_ID, text, reply_markup=admin_order_kb(order.id), parse_mode="HTML")
    except Exception as e:
        print("Ошибка отправки админу:", e)

    await message.answer(
        f"✅ Заказ №{order.id} отправлен администратору.\n"
        f"К оплате: <b>{int(total_with_delivery)}₽</b>\n"
        f"Ожидайте подтверждения.",
        reply_markup=cart_kb(False),
        parse_mode="HTML",
        )
