import asyncio
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, func
from database.db import SessionLocal
from database.models import Category, Product, Order, OrderItem, User, Promocode
from config import (
    ADMIN_ID, REFERRAL_MILESTONE, REFERRAL_MILESTONE_DISCOUNT
)
from keyboards.inline import categories_kb, admin_menu_kb, admin_order_kb
from utils.states import AddProduct, EditProduct, DelProduct
from utils.promo import gen_promo

router = Router()


def is_admin(uid: int) -> bool:
    return uid == ADMIN_ID


async def _auto_delete(bot, chat_id: int, message_id: int, delay: int = 0):
    if delay:
        await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass


async def cleanup_messages(bot, chat_id: int, message_ids: list[int]):
    for mid in message_ids:
        await _auto_delete(bot, chat_id, mid)


async def _delete_user_msg(msg: Message):
    try:
        await msg.delete()
    except Exception:
        pass


@router.message(Command("admin"))
async def admin_panel(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    await msg.answer(
        "👑 <b>Админ-панель Dead Smoke Store</b>",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML",
    )


# ======================== ДОБАВИТЬ ТОВАР ========================
@router.callback_query(F.data == "admin:add_product")
async def add_product_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    async with SessionLocal() as s:
        cats = (await s.execute(select(Category).order_by(Category.id))).scalars().all()
    sent = await cb.message.edit_text("Выбери раздел:", reply_markup=categories_kb(cats))
    await state.update_data(cleanup_ids=[sent.message_id], chat_id=sent.chat.id)
    await state.set_state(AddProduct.category)


@router.callback_query(AddProduct.category, F.data.regexp(r"^cat:\d+$"))
async def add_product_cat(cb: CallbackQuery, state: FSMContext):
    cat_id = int(cb.data.split(":")[1])
    await state.update_data(category_id=cat_id)
    sent = await cb.message.edit_text("Введи <b>бренд</b> товара:", parse_mode="HTML")
    data = await state.get_data()
    ids = data.get("cleanup_ids", [])
    ids.append(sent.message_id)
    await state.update_data(cleanup_ids=ids)
    await state.set_state(AddProduct.brand)


@router.message(AddProduct.brand)
async def add_product_brand(msg: Message, state: FSMContext):
    await _delete_user_msg(msg)
    await state.update_data(brand=msg.text.strip())
    sent = await msg.answer("Введи <b>вкус</b> (или вариант):", parse_mode="HTML")
    data = await state.get_data()
    ids = data.get("cleanup_ids", [])
    ids.append(sent.message_id)
    await state.update_data(cleanup_ids=ids)
    await state.set_state(AddProduct.flavor)


@router.message(AddProduct.flavor)
async def add_product_flavor(msg: Message, state: FSMContext):
    await _delete_user_msg(msg)
    await state.update_data(flavor=msg.text.strip())
    sent = await msg.answer("Введи <b>цену</b> (только число, ₽):", parse_mode="HTML")
    data = await state.get_data()
    ids = data.get("cleanup_ids", [])
    ids.append(sent.message_id)
    await state.update_data(cleanup_ids=ids)
    await state.set_state(AddProduct.price)


@router.message(AddProduct.price)
async def add_product_price(msg: Message, state: FSMContext):
    await _delete_user_msg(msg)
    try:
        price = float(msg.text.replace(",", ".").replace("₽", "").strip())
    except ValueError:
        sent = await msg.answer("❌ Некорректная цена. Введи число:")
        data = await state.get_data()
        ids = data.get("cleanup_ids", [])
        ids.append(sent.message_id)
        await state.update_data(cleanup_ids=ids)
        return

    data = await state.get_data()
    async with SessionLocal() as s:
        max_num = (await s.execute(
            select(func.max(Product.number)).where(Product.category_id == data["category_id"])
        )).scalar() or 0
        p = Product(
            category_id=data["category_id"],
            number=max_num + 1,
            brand=data["brand"],
            flavor=data["flavor"],
            price=price,
            in_stock=True,
        )
        s.add(p)
        await s.commit()

    chat_id = data.get("chat_id") or msg.chat.id
    await cleanup_messages(msg.bot, chat_id, data.get("cleanup_ids", []))

    final = await msg.answer(
        f"✅ Добавлено: <b>{data['brand']}</b> — {data['flavor']} — {int(price)}₽ (№{max_num+1})",
        parse_mode="HTML",
    )
    asyncio.create_task(_auto_delete(msg.bot, chat_id, final.message_id, 5))
    await state.clear()


# ======================== РЕДАКТИРОВАТЬ ТОВАР ========================
@router.callback_query(F.data == "admin:edit_product")
async def edit_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    async with SessionLocal() as s:
        cats = (await s.execute(select(Category).order_by(Category.id))).scalars().all()
    sent = await cb.message.edit_text("Выбери раздел:", reply_markup=categories_kb(cats))
    await state.update_data(cleanup_ids=[sent.message_id], chat_id=sent.chat.id)
    await state.set_state(EditProduct.category)


@router.callback_query(EditProduct.category, F.data.regexp(r"^cat:\d+$"))
async def edit_cat(cb: CallbackQuery, state: FSMContext):
    cat_id = int(cb.data.split(":")[1])
    await state.update_data(category_id=cat_id)
    async with SessionLocal() as s:
        products = (await s.execute(
            select(Product).where(Product.category_id == cat_id).order_by(Product.number)
        )).scalars().all()
    if not products:
        await cb.message.edit_text("В разделе нет товаров.")
        await state.clear()
        return
    text = "Введи номер товара:\n" + "\n".join(
        f"{p.number}. {p.brand} — {p.flavor} — {int(p.price)}₽" for p in products
    )
    sent = await cb.message.edit_text(text)
    data = await state.get_data()
    ids = data.get("cleanup_ids", [])
    ids.append(sent.message_id)
    await state.update_data(cleanup_ids=ids)
    await state.set_state(EditProduct.number)


@router.message(EditProduct.number)
async def edit_number(msg: Message, state: FSMContext):
    await _delete_user_msg(msg)
    data = await state.get_data()
    try:
        num = int(msg.text.strip())
    except ValueError:
        sent = await msg.answer("Введи число.")
        ids = data.get("cleanup_ids", [])
        ids.append(sent.message_id)
        await state.update_data(cleanup_ids=ids)
        return

    async with SessionLocal() as s:
        p = (await s.execute(
            select(Product).where(
                Product.category_id == data["category_id"], Product.number == num
            )
        )).scalar_one_or_none()
    if not p:
        sent = await msg.answer("Товар не найден.")
        ids = data.get("cleanup_ids", [])
        ids.append(sent.message_id)
        await state.update_data(cleanup_ids=ids)
        return

    await state.update_data(product_id=p.id)
    kb = InlineKeyboardBuilder()
    kb.button(text="Бренд", callback_data="editfield:brand")
    kb.button(text="Вкус", callback_data="editfield:flavor")
    kb.button(text="Цена", callback_data="editfield:price")
    kb.adjust(1)
    sent = await msg.answer(
        f"Что меняем у «{p.brand} — {p.flavor}»?",
        reply_markup=kb.as_markup()
    )
    ids = data.get("cleanup_ids", [])
    ids.append(sent.message_id)
    await state.update_data(cleanup_ids=ids)
    await state.set_state(EditProduct.field)


@router.callback_query(EditProduct.field, F.data.startswith("editfield:"))
async def edit_field(cb: CallbackQuery, state: FSMContext):
    field = cb.data.split(":")[1]
    await state.update_data(field=field)
    label = {"brand": "бренд", "flavor": "вкус", "price": "цену"}[field]
    sent = await cb.message.edit_text(f"Введи новый {label}:")
    data = await state.get_data()
    ids = data.get("cleanup_ids", [])
    ids.append(sent.message_id)
    await state.update_data(cleanup_ids=ids)
    await state.set_state(EditProduct.value)


@router.message(EditProduct.value)
async def edit_value(msg: Message, state: FSMContext):
    await _delete_user_msg(msg)
    data = await state.get_data()
    field = data["field"]
    value = msg.text.strip()
    if field == "price":
        try:
            value = float(value.replace(",", ".").replace("₽", ""))
        except ValueError:
            sent = await msg.answer("Введи число.")
            ids = data.get("cleanup_ids", [])
            ids.append(sent.message_id)
            await state.update_data(cleanup_ids=ids)
            return

    async with SessionLocal() as s:
        p = await s.get(Product, data["product_id"])
        setattr(p, field, value)
        await s.commit()

    chat_id = data.get("chat_id", msg.chat.id)
    await cleanup_messages(msg.bot, chat_id, data.get("cleanup_ids", []))

    final = await msg.answer(f"✅ Обновлено: {p.brand} — {p.flavor} — {int(p.price)}₽")
    asyncio.create_task(_auto_delete(msg.bot, chat_id, final.message_id, 5))
    await state.clear()


# ======================== УДАЛИТЬ ТОВАР ========================
@router.callback_query(F.data == "admin:del_product")
async def del_product_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    async with SessionLocal() as s:
        cats = (await s.execute(select(Category).order_by(Category.id))).scalars().all()
    sent = await cb.message.edit_text("Выбери раздел:", reply_markup=categories_kb(cats))
    await state.update_data(cleanup_ids=[sent.message_id], chat_id=sent.chat.id)
    await state.set_state(DelProduct.category)


@router.callback_query(DelProduct.category, F.data.regexp(r"^cat:\d+$"))
async def del_product_cat(cb: CallbackQuery, state: FSMContext):
    cat_id = int(cb.data.split(":")[1])
    await state.update_data(category_id=cat_id)
    async with SessionLocal() as s:
        products = (await s.execute(
            select(Product).where(Product.category_id == cat_id).order_by(Product.number)
        )).scalars().all()
    if not products:
        await cb.message.edit_text("В разделе нет товаров.")
        await state.clear()
        return
    text = "Введи номер товара для удаления:\n" + "\n".join(
        f"{p.number}. {p.brand} — {p.flavor} — {int(p.price)}₽" for p in products
    )
    sent = await cb.message.edit_text(text)
    data = await state.get_data()
    ids = data.get("cleanup_ids", [])
    ids.append(sent.message_id)
    await state.update_data(cleanup_ids=ids)
    await state.set_state(DelProduct.number)


@router.message(DelProduct.number)
async def del_product_number(msg: Message, state: FSMContext):
    await _delete_user_msg(msg)
    data = await state.get_data()
    try:
        num = int(msg.text.strip())
    except ValueError:
        sent = await msg.answer("Введи число.")
        ids = data.get("cleanup_ids", [])
        ids.append(sent.message_id)
        await state.update_data(cleanup_ids=ids)
        return

    chat_id = data.get("chat_id", msg.chat.id)
    async with SessionLocal() as s:
        p = (await s.execute(
            select(Product).where(
                Product.category_id == data["category_id"], Product.number == num
            )
        )).scalar_one_or_none()
        if not p:
            await cleanup_messages(msg.bot, chat_id, data.get("cleanup_ids", []))
            final = await msg.answer("Товар не найден.")
            asyncio.create_task(_auto_delete(msg.bot, chat_id, final.message_id, 3))
            await state.clear()
            return
        await s.delete(p)
        await s.commit()

    await cleanup_messages(msg.bot, chat_id, data.get("cleanup_ids", []))
    final = await msg.answer(f"🗑 Удалён товар №{num}.")
    asyncio.create_task(_auto_delete(msg.bot, chat_id, final.message_id, 5))
    await state.clear()


# ======================== ПРИЁМ / ОТКЛОНЕНИЕ ЗАКАЗА ========================
@router.callback_query(F.data.startswith("order:"))
async def process_order(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("Не для тебя кнопка 🙂", show_alert=True)
        return
    _, action, order_id = cb.data.split(":")
    order_id = int(order_id)

    async with SessionLocal() as s:
        order = await s.get(Order, order_id)
        if not order or order.status != "pending":
            await cb.answer("Заказ уже обработан.", show_alert=True)
            return

        items = (await s.execute(
            select(OrderItem, Product).join(Product, OrderItem.product_id == Product.id)
            .where(OrderItem.order_id == order_id)
        )).all()
        buyer = await s.get(User, order.user_id)

        if action == "approve":
            order.status = "approved"
            for _, p in items:
                await s.delete(p)
            buyer.balance = (buyer.balance or 0) + order.total

            # === РЕФЕРАЛЬНАЯ ЛОГИКА ===
            if buyer.referrer_id and not buyer.first_purchase_done:
                bonus = round(order.total * 0.15, 2)
                code = gen_promo()
                while await s.get(Promocode, code):
                    code = gen_promo()
                s.add(Promocode(
                    code=code,
                    owner_id=buyer.referrer_id,
                    kind="fixed",
                    amount=bonus,
                    created_by="ref",
                ))

                ref_user = await s.get(User, buyer.referrer_id)
                if ref_user:
                    ref_user.referrals_count += 1

                    if ref_user.referrals_count >= ref_user.next_bonus_at:
                        milestone_code = gen_promo()
                        while await s.get(Promocode, milestone_code):
                            milestone_code = gen_promo()
                        s.add(Promocode(
                            code=milestone_code,
                            owner_id=buyer.referrer_id,
                            kind="percent",
                            amount=REFERRAL_MILESTONE_DISCOUNT,
                            created_by="ref",
                        ))
                        ref_user.next_bonus_at += REFERRAL_MILESTONE

                        try:
                            await cb.bot.send_message(
                                buyer.referrer_id,
                                f"🎉 Ты пригласил {ref_user.referrals_count} <b>купивших</b> друзей!\n"
                                f"Вот промокод на <b>−{int(REFERRAL_MILESTONE_DISCOUNT)}%</b>:\n"
                                f"<code>{milestone_code}</code>",
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass

                    try:
                        await cb.bot.send_message(
                            buyer.referrer_id,
                            f"🎁 Ваш реферал совершил первую покупку!\n"
                            f"Вам начислен промокод на <b>{int(bonus)}₽</b>:\n"
                            f"<code>{code}</code>",
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass

                buyer.first_purchase_done = True

            # списание использованных промо
            if order.promo_codes:
                for pc in order.promo_codes.split(","):
                    promo = await s.get(Promocode, pc)
                    if promo:
                        promo.used_count += 1
                        if promo.used_count >= promo.max_uses:
                            promo.used = True

            await cb.bot.send_message(
                buyer.id,
                f"✅ Ваш заказ №{order.id} подтверждён! Спасибо за покупку 💚"
            )
            await cb.message.edit_text(
                cb.message.html_text + "\n\n✅ <b>Подтверждён</b>",
                parse_mode="HTML"
            )
            asyncio.create_task(_auto_delete(cb.bot, cb.message.chat.id, cb.message.message_id, 3))

        else:  # reject
            order.status = "rejected"
            for _, p in items:
                p.in_stock = True
            await cb.bot.send_message(
                buyer.id,
                f"❌ Ваш заказ №{order.id} отклонён администратором."
            )
            await cb.message.edit_text(
                cb.message.html_text + "\n\n❌ <b>Отклонён</b>",
                parse_mode="HTML"
            )
            asyncio.create_task(_auto_delete(cb.bot, cb.message.chat.id, cb.message.message_id, 3))

        await s.commit()
