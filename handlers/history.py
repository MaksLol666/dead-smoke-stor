from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select
from database.db import SessionLocal
from database.models import Order
from keyboards.inline import back_to_menu_kb

router = Router()


@router.callback_query(F.data == "history:show")
async def show_history(cb: CallbackQuery):
    uid = cb.from_user.id
    async with SessionLocal() as s:
        orders = (await s.execute(
            select(Order).where(Order.user_id == uid)
            .order_by(Order.created_at.desc()).limit(10)
        )).scalars().all()

    if not orders:
        await cb.message.edit_text(
            "📜 У тебя пока нет заказов.\n\nЗагляни в 📂 Каталог!",
            reply_markup=back_to_menu_kb(),
        )
        return

    status_emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}
    status_text = {"pending": "В обработке", "approved": "Выполнен", "rejected": "Отклонён"}

    lines = ["📜 <b>История заказов:</b>\n"]
    for o in orders:
        emoji = status_emoji.get(o.status, "❔")
        st = status_text.get(o.status, o.status)
        date = o.created_at.strftime("%d.%m.%Y")
        lines.append(f"{emoji} Заказ №{o.id} — {int(o.total)}₽ — {date} — <i>{st}</i>")

    await cb.message.edit_text("\n".join(lines), reply_markup=back_to_menu_kb(), parse_mode="HTML")
