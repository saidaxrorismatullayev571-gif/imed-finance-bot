"""Sozlash amallari — boshlang'ich balans va valyuta kursi kiritish.

Bular Faza 1 ni yakunlaydi: `opening` turidagi tranzaksiya bilan kassaga
ish boshidagi mavjud pulni yozish, va `exchange_rates` jadvaliga kunlik
kursni kiritish (UZS bo'lmagan kassalar shusiz ishlamaydi)."""

from decimal import Decimal, InvalidOperation

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.db import acquire

router = Router()

NON_UZS = ("USD",)


def _parse_amount(raw: str) -> Decimal | None:
    cleaned = raw.strip().replace(" ", "").replace(",", "")
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    return value if value > 0 else None


async def _require_admin(message: Message, conn) -> int | None:
    user = await conn.fetchrow(
        "SELECT id, role FROM users WHERE telegram_id = $1 AND is_active",
        message.from_user.id,
    )
    if user is None:
        await message.answer("Avval ro'yxatdan o'ting: /start")
        return None
    if user["role"] != "admin":
        await message.answer("Bu amalni faqat administrator bajara oladi.")
        return None
    return user["id"]


def _cancel_row() -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="setupcancel")]


# ----------------- BOSHLANG'ICH BALANS -----------------


class OpeningBalance(StatesGroup):
    choosing_wallet = State()
    entering_amount = State()


@router.message(Command("boshlangich"))
async def cmd_opening(message: Message, state: FSMContext) -> None:
    async with acquire() as conn:
        admin_id = await _require_admin(message, conn)
        if admin_id is None:
            return
        wallets = await conn.fetch(
            "SELECT id, name, currency FROM wallets WHERE is_active ORDER BY id"
        )
    if not wallets:
        await message.answer("Faol kassa topilmadi.")
        return

    rows = [
        [InlineKeyboardButton(
            text=f"{w['name']} ({w['currency']})", callback_data=f"opw:{w['id']}"
        )]
        for w in wallets
    ]
    rows.append(_cancel_row())
    await state.clear()
    await state.set_state(OpeningBalance.choosing_wallet)
    await state.update_data(admin_id=admin_id)
    await message.answer(
        "Boshlang'ich balans — qaysi kassa uchun?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(OpeningBalance.choosing_wallet, F.data.startswith("opw:"))
async def cb_opening_wallet(callback: CallbackQuery, state: FSMContext) -> None:
    wallet_id = int(callback.data.split(":", 1)[1])
    async with acquire() as conn:
        wallet = await conn.fetchrow(
            "SELECT id, name, currency FROM wallets WHERE id = $1 AND is_active", wallet_id
        )
    if wallet is None:
        await callback.answer("Kassa topilmadi.", show_alert=True)
        return

    fx_rate = Decimal("1")
    if wallet["currency"] != "UZS":
        async with acquire() as conn:
            rate = await conn.fetchval(
                "SELECT rate_uzs FROM exchange_rates WHERE currency = $1 "
                "ORDER BY fetched_at DESC LIMIT 1",
                wallet["currency"],
            )
        if rate is None:
            await callback.message.edit_text(
                f"{wallet['currency']} uchun kurs kiritilmagan. Avval /kurs bilan kiriting."
            )
            await state.clear()
            await callback.answer()
            return
        fx_rate = rate

    await state.update_data(
        wallet_id=wallet["id"], currency=wallet["currency"], fx_rate=str(fx_rate)
    )
    await state.set_state(OpeningBalance.entering_amount)
    await callback.message.edit_text(
        f"{wallet['name']} — boshlang'ich summani kiriting ({wallet['currency']}):"
    )
    await callback.answer()


@router.message(OpeningBalance.entering_amount, F.text)
async def msg_opening_amount(message: Message, state: FSMContext) -> None:
    amount = _parse_amount(message.text)
    if amount is None:
        await message.answer("Noto'g'ri summa. Faqat musbat raqam kiriting.")
        return

    data = await state.get_data()
    await state.clear()
    fx_rate = Decimal(data["fx_rate"])
    amount_uzs = (amount * fx_rate).quantize(Decimal("0.01"))
    admin_id = data["admin_id"]

    async with acquire(actor_id=admin_id) as conn:
        await conn.execute(
            """INSERT INTO transactions
               (kind, wallet_id, amount, currency, fx_rate, amount_uzs, description, created_by)
               VALUES ('opening', $1, $2, $3::currency_code, $4, $5, $6, $7)""",
            data["wallet_id"],
            amount,
            data["currency"],
            fx_rate,
            amount_uzs,
            "Boshlang'ich balans",
            admin_id,
        )
    await message.answer(
        f"✅ Boshlang'ich balans qayd etildi: {amount} {data['currency']} (≈{amount_uzs} UZS)"
    )


# ----------------- VALYUTA KURSI -----------------


class SetRate(StatesGroup):
    choosing_currency = State()
    entering_rate = State()


@router.message(Command("kurs"))
async def cmd_rate(message: Message, state: FSMContext) -> None:
    async with acquire() as conn:
        admin_id = await _require_admin(message, conn)
        if admin_id is None:
            return

    rows = [[InlineKeyboardButton(text=c, callback_data=f"fxc:{c}")] for c in NON_UZS]
    rows.append(_cancel_row())
    await state.clear()
    await state.set_state(SetRate.choosing_currency)
    await state.update_data(admin_id=admin_id)
    await message.answer(
        "Qaysi valyuta kursi? (1 birlik necha UZS)",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(SetRate.choosing_currency, F.data.startswith("fxc:"))
async def cb_rate_currency(callback: CallbackQuery, state: FSMContext) -> None:
    currency = callback.data.split(":", 1)[1]
    if currency not in NON_UZS:
        await callback.answer("Noto'g'ri valyuta.", show_alert=True)
        return
    await state.update_data(currency=currency)
    await state.set_state(SetRate.entering_rate)
    await callback.message.edit_text(
        f"1 {currency} necha UZS? (masalan: 12650)"
    )
    await callback.answer()


@router.message(SetRate.entering_rate, F.text)
async def msg_rate_value(message: Message, state: FSMContext) -> None:
    rate = _parse_amount(message.text)
    if rate is None:
        await message.answer("Noto'g'ri kurs. Faqat musbat raqam kiriting.")
        return

    data = await state.get_data()
    await state.clear()
    async with acquire() as conn:
        await conn.execute(
            "INSERT INTO exchange_rates (currency, rate_uzs, source) "
            "VALUES ($1::currency_code, $2, 'manual')",
            data["currency"],
            rate,
        )
    await message.answer(f"✅ Kurs saqlandi: 1 {data['currency']} = {rate} UZS")


# ----------------- UMUMIY BEKOR QILISH -----------------


@router.callback_query(F.data == "setupcancel")
async def cb_setup_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Bekor qilindi.")
    await callback.answer()
