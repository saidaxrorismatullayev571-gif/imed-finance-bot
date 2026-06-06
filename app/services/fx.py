"""Valyuta kurslari (CBU monitoring) — multi-valyuta hisob-kitobi uchun.

UZS asosiy valyuta. USD uchun kurs CBU dan olinadi va `exchange_rates` ga saqlanadi.
Tranzaksiyada:  amount_uzs = amount * fx_rate  (UZS uchun fx_rate = 1).
"""
import logging
from decimal import Decimal

import aiohttp

from app.db import acquire

log = logging.getLogger("imed-finance-bot.fx")

# CBU rasmiy JSON API — barcha valyutalar ro'yxati (USD ham ichida)
CBU_URL = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/"
_TIMEOUT = aiohttp.ClientTimeout(total=15)

# CBU mavjud bo'lmaganda zaxira kurs (faqat birinchi marta, baza bo'sh bo'lsa)
_FALLBACK_USD = Decimal("12600")


async def fetch_and_store_cbu(actor_id: int | None = None) -> Decimal | None:
    """CBU dan USD kursini olib `exchange_rates` ga yozadi. Kursni qaytaradi."""
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.get(CBU_URL) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
    except Exception as exc:  # tarmoq xatosi — log qilamiz, botni yiqitmaymiz
        log.warning("CBU kursini olishda xato: %s", exc)
        return None

    rate: Decimal | None = None
    for item in data or []:
        if item.get("Ccy") == "USD":
            try:
                rate = Decimal(str(item["Rate"]))
            except (KeyError, ArithmeticError, ValueError):
                rate = None
            break

    if rate is None or rate <= 0:
        log.warning("CBU javobida USD kursi topilmadi")
        return None

    async with acquire(actor_id) as conn:
        await conn.execute(
            "INSERT INTO exchange_rates (currency, rate_uzs, source) VALUES ('USD', $1, 'CBU')",
            rate,
        )
    log.info("USD kursi yangilandi: %s", rate)
    return rate


async def get_rate(currency: str) -> Decimal:
    """Berilgan valyutaning UZS ga so'nggi kursini qaytaradi (UZS uchun 1)."""
    if currency == "UZS":
        return Decimal(1)
    async with acquire() as conn:
        row = await conn.fetchrow(
            "SELECT rate_uzs FROM exchange_rates WHERE currency = $1 "
            "ORDER BY fetched_at DESC LIMIT 1",
            currency,
        )
    if row:
        return Decimal(row["rate_uzs"])
    # Baza bo'sh — bir marta CBU dan urinib ko'ramiz, bo'lmasa zaxira
    fetched = await fetch_and_store_cbu()
    return fetched if fetched is not None else _FALLBACK_USD


def to_uzs(amount: Decimal, fx_rate: Decimal) -> Decimal:
    """amount_uzs ni 2 kasrga yaxlitlab hisoblaydi."""
    return (Decimal(amount) * Decimal(fx_rate)).quantize(Decimal("0.01"))
