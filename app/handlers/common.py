"""Handlerlar uchun umumiy yordamchilar: foydalanuvchi, summa parser, formatlash."""
from datetime import date, datetime
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


_DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y")


def parse_date(text: str) -> date | None:
    """Sanani ajratadi: "2026-06-30", "30.06.2026", "30/06/2026". Xato bo'lsa None."""
    raw = (text or "").strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def fmt_date(value) -> str:
    """date/None ni ko'rsatadi: 2026-06-30 -> "30.06.2026", None -> "—"."""
    if value is None:
        return "—"
    return value.strftime("%d.%m.%Y")


def mask_phone(phone: str | None) -> str:
    """Telefon raqamini maskalaydi: "+998901234567" -> "+998*****4567"."""
    if not phone:
        return "—"
    raw = phone.strip()
    if len(raw) <= 6:
        return raw
    return raw[:4] + "*" * (len(raw) - 8) + raw[-4:]
