from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📂 Каталог", callback_data="cat:open")
    kb.button(text="🛒 Корзина", callback_data="cart:view")
    kb.button(text="👤 Мой профиль", callback_data="profile:show")
    kb.button(text="📜 История заказов", callback_data="history:show")
    kb.button(text="🏆 Топ-10 покупателей", callback_data="top:show")
    kb.button(text="👥 Топ реферов", callback_data="topref:show")
    kb.button(text="🎟 Мои промо", callback_data="promo:mine")
    kb.adjust(2, 2, 2, 1)
    return kb.as_markup()


def categories_kb(categories):
    kb = InlineKeyboardBuilder()
    for c in categories:
        kb.button(text=c.name, callback_data=f"cat:{c.id}")
    kb.button(text="⬅️ В меню", callback_data="menu:main")
    kb.adjust(2, 2, 2, 1, 1)
    return kb.as_markup()


def products_kb(products):
    kb = InlineKeyboardBuilder()
    for p in products:
        kb.button(text=str(p.number), callback_data=f"prod:{p.id}")
    kb.button(text="🛒 Корзина", callback_data="cart:view")
    kb.button(text="⬅️ Назад", callback_data="cat:open")
    kb.adjust(5, 1, 1)
    return kb.as_markup()


def cart_kb(has_items: bool):
    kb = InlineKeyboardBuilder()
    if has_items:
        kb.button(text="✅ Оформить заказ", callback_data="cart:checkout")
        kb.button(text="🎟 Ввести промокод", callback_data="promo:enter")
        kb.button(text="🗑 Очистить корзину", callback_data="cart:clear")
    kb.button(text="⬅️ В меню", callback_data="menu:main")
    kb.adjust(1)
    return kb.as_markup()


def back_to_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ В меню", callback_data="menu:main")
    return kb.as_markup()


def profile_kb(ref_link: str):
    kb = InlineKeyboardBuilder()
    share_text = (
        f"{ref_link}\n"
        f"Dead Smoke Store💨 — перестань ждать ответа администратора по наличию. "
        f"Всегда весь актуальный ассортимент внутри бота! Не упусти.."
    )
    kb.button(
        text="📤 Поделиться ссылкой",
        switch_inline_query=share_text,
    )
    kb.button(text="⬅️ В меню", callback_data="menu:main")
    kb.adjust(1)
    return kb.as_markup()


def admin_order_kb(order_id: int):
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Принять", callback_data=f"order:approve:{order_id}")
    kb.button(text="❌ Отклонить", callback_data=f"order:reject:{order_id}")
    kb.adjust(2)
    return kb.as_markup()


def admin_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить товар", callback_data="admin:add_product")
    kb.button(text="✏️ Редактировать товар", callback_data="admin:edit_product")
    kb.button(text="🗑 Удалить товар", callback_data="admin:del_product")
    kb.adjust(1)
    return kb.as_markup()


def review_kb(order_id: int):
    kb = InlineKeyboardBuilder()
    kb.button(text="📝 Оставить отзыв", callback_data=f"review:write:{order_id}")
    return kb.as_markup()


def review_rating_kb(order_id: int):
    kb = InlineKeyboardBuilder()
    kb.button(text="1 ⭐", callback_data=f"review:rate:{order_id}:1")
    kb.button(text="2 ⭐", callback_data=f"review:rate:{order_id}:2")
    kb.button(text="3 ⭐", callback_data=f"review:rate:{order_id}:3")
    kb.button(text="4 ⭐", callback_data=f"review:rate:{order_id}:4")
    kb.button(text="5 ⭐", callback_data=f"review:rate:{order_id}:5")
    kb.adjust(5)
    return kb.as_markup()


def delivery_choice_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🏠 Самовывоз", callback_data="delivery:pickup")
    kb.button(text="🚚 СДЭК (500₽)", callback_data="delivery:cdek")
    kb.adjust(1)
    return kb.as_markup()
