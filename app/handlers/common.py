"""Handlerlar uchun umumiy yordamchilar: foydalanuvchi, summa parser, formatlash."""
from decimal import Decimal, InvalidOperation

import asyncpg

from app.db import acquire


async def get_current_user(telegram_id: int) -> asyncpg.Record | None:
    """telegram_id bo'yicha faol foydalanuvchini qaytaradi (id, role, full_name)."""
    async with acquire() as conn:
        return await conn.fetchrow(
            "SELECT id, role, full_name FROM users WHERE telegram_id = $1 AND is_active",
            telegram_id,
        )


def parse_amount(text: str) -> Decimal | None:
    """Matndan summani ajratadi. "1 000 000", "1,000,000", "1000000.50" — hammasi bo'ladi.

    Musbat bo'lmasa yoki noto'g'ri bo'lsa None qaytaradi.
    """
    cleaned = (text or "").strip().replace(" ", "").replace(",", "")
    if not cleaned:
        return None
    try:
        value = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None
    if value <= 0:
        return None
    # NUMERIC(18,2) — ikki kasrgacha yaxlitlaymiz
    return value.quantize(Decimal("0.01"))


def fmt_money(amount, currency: str = "UZS") -> str:
    """Summani chiroyli ko'rsatadi: 1234567.5 -> "1 234 567.50 UZS"."""
    value = Decimal(amount)
    whole, _, frac = f"{value:.2f}".partition(".")
    sign = "-" if whole.startswith("-") else ""
    whole = whole.lstrip("-")
    grouped = f"{int(whole):,}".replace(",", " ")
    return f"{sign}{grouped}.{frac} {currency}"
