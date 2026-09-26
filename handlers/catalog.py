from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select
from database.db import SessionLocal
from database.models import Category, Product, CartItem
from keyboards.inline import categories_kb, products_kb

router = Router()


@router.callback_query(F.data == "cat:open")
async def open_catalog(cb: CallbackQuery):
    async with SessionLocal() as s:
        cats = (await s.execute(select(Category).order_by(Category.id))).scalars().all()
    await cb.message.edit_text(
        "📂 <b>Каталог Dead Smoke Store</b>\n\nВыбери раздел:",
        reply_markup=categories_kb(cats),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "cat:back")
async def back_to_cats(cb: CallbackQuery):
    await open_catalog(cb)


@router.callback_query(F.data.regexp(r"^cat:\d+$"))
async def show_category(cb: CallbackQuery):
    cat_id = int(cb.data.split(":")[1])
    async with SessionLocal() as s:
        cat = await s.get(Category, cat_id)
        products = (await s.execute(
            select(Product).where(
                Product.category_id == cat_id, Product.in_stock == True
            ).order_by(Product.number)
        )).scalars().all()

    if not products:
        await cb.answer("В этом разделе пока пусто", show_alert=True)
        return

    # пустая строка между товарами — для читаемости
    lines = [f"{p.number}. {p.brand} — {p.flavor} — {int(p.price)}₽" for p in products]
    body = "\n\n".join(lines)

    text = f"📂 <b>{cat.name}</b>\n\n{body}\n\nНажми номер, чтобы добавить в корзину."
    await cb.message.edit_text(text, reply_markup=products_kb(products), parse_mode="HTML")


@router.callback_query(F.data.startswith("prod:"))
async def add_to_cart(cb: CallbackQuery):
    product_id = int(cb.data.split(":")[1])
    user_id = cb.from_user.id

    async with SessionLocal() as s:
        product = await s.get(Product, product_id)
        if not product or not product.in_stock:
            await cb.answer("Товар недоступен", show_alert=True)
            return

        # проверяем, уже в корзине?
        existing = (await s.execute(
            select(CartItem).where(
                CartItem.user_id == user_id,
                CartItem.product_id == product_id,
            )
        )).scalar_one_or_none()

        if existing:
            await cb.answer(
                f"⚠️ {product.brand} {product.flavor} уже в корзине",
                show_alert=False,
            )
            return

        s.add(CartItem(user_id=user_id, product_id=product_id, reserved=False))
        await s.commit()

    await cb.answer(f"✅ {product.brand} {product.flavor} добавлен в корзину")
