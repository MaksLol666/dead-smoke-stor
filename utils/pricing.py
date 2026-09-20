from sqlalchemy import select
from database.db import SessionLocal
from database.models import Promocode


async def calc_discount(applied_codes: list[str]) -> tuple[float, float]:
    """
    Возвращает (percent_discount, fixed_discount).
    percent — суммарный % (макс 100), fixed — суммарная ₽ скидка.
    """
    if not applied_codes:
        return 0.0, 0.0

    async with SessionLocal() as s:
        promos = (await s.execute(
            select(Promocode).where(Promocode.code.in_(applied_codes))
        )).scalars().all()

    percent = 0.0
    fixed = 0.0
    for p in promos:
        if p.kind == "percent":
            percent += p.amount
        else:
            fixed += p.amount
    percent = min(percent, 100.0)
    return percent, fixed
