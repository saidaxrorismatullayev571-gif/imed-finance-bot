"""Kassalar orasida pul o'tkazish (transfer) — Faza 2 boshlanishi.

Har bir transfer ikkita bog'langan tranzaksiya sifatida yoziladi
(`transfer_out` manba kassadan, `transfer_in` maqsad kassaga), ikkalasi
bitta `transfer_group_id` bilan bog'lanadi va bitta DB tranzaksiyasida
atomik tarzda yoziladi — biri muvaffaqiyatsiz bo'lsa, ikkalasi ham
qaytariladi.

Hozircha faqat BIR XIL valyutadagi kassalar orasida transfer qo'llab-
quvvatlanadi (valyuta konvertatsiyasi kerak bo'lgan transfer — keyingi
faza)."""

import uuid
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
from app.handlers.finance import CAN_RECORD_ROLES, _get_user

router = Router()


class TransferFlow(StatesGroup):
    choosing_source = State()
    choosing_dest = State()
    entering_amount = State()
    entering_description = State()


def _cancel_row() -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="txcancel")]


def _wallets_kb(wallets, prefix: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"{w['name']} ({w['currency']})", callback_data=f"{prefix}{w['id']}")]
        for w in wallets
    ]
    rows.append(_cancel_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("transfer"))
async def cmd_transfer(message: Message, state: FSMContext) -> None:
    async with acquire() as conn:
        user = await _get_user(conn, message.from_user.id)
        if user is None:
            await message.answer("Avval ro'yxatdan o'ting: /start")
            return
        if user["role"] not in CAN_RECORD_ROLES:
            await message.answer("Sizda bu amalni bajarish huquqi yo'q.")
            return
        wallets = await conn.fetch(
            "SELECT id, name, currency FROM wallets WHERE is_active ORDER BY id"
        )

    if len(wallets) < 2:
        await message.answer("Transfer uchun kamida 2 ta faol kassa kerak.")
        return

    await state.clear()
    await state.set_state(TransferFlow.choosing_source)
    await state.update_data(admin_id=user["id"])
    await message.answer(
        "Transfer — qaysi kassaDAN pul chiqadi?", reply_markup=_wallets_kb(wallets, "trsrc:")
    )


@router.callback_query(TransferFlow.choosing_source, F.data.startswith("trsrc:"))
async def cb_source_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    source_id = int(callback.data.split(":", 1)[1])
    async with acquire() as conn:
        source = await conn.fetchrow(
            "SELECT id, name, currency FROM wallets WHERE id = $1 AND is_active", source_id
        )
        if source is None:
            await callback.answer("Kassa topilmadi.", show_alert=True)
            return
        dest_candidates = await conn.fetch(
            "SELECT id, name, currency FROM wallets "
            "WHERE is_active AND id != $1 AND currency = $2 ORDER BY id",
            source_id, source["currency"],
        )

    if not dest_candidates:
        await callback.message.edit_text(
            f"{source['name']} bilan bir xil valyutadagi ({source['currency']}) "
            "boshqa faol kassa yo'q. Hozircha faqat bir xil valyutadagi kassalar "
            "orasida transfer mumkin."
        )
        await state.clear()
        await callback.answer()
        return

    await state.update_data(source_id=source["id"], currency=source["currency"])
    await state.set_state(TransferFlow.choosing_dest)
    await callback.message.edit_text(
        f"{source['name']} dan — qaysi kassaGA o'tkazasiz?",
        reply_markup=_wallets_kb(dest_candidates, "trdst:"),
    )
    await callback.answer()


@router.callback_query(TransferFlow.choosing_dest, F.data.startswith("trdst:"))
async def cb_dest_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    dest_id = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    async with acquire() as conn:
        dest = await conn.fetchrow(
            "SELECT id, name, currency FROM wallets WHERE id = $1 AND is_active "
            "AND currency = $2 AND id != $3",
            dest_id, data["currency"], data["source_id"],
        )
    if dest is None:
        await callback.answer("Kassa topilmadi yoki valyutasi mos kelmaydi.", show_alert=True)
        return

    await state.update_data(dest_id=dest["id"])
    await state.set_state(TransferFlow.entering_amount)
    await callback.message.edit_text(f"Summani kiriting ({data['currency']}):")
    await callback.answer()


@router.message(TransferFlow.entering_amount, F.text)
async def msg_amount_entered(message: Message, state: FSMContext) -> None:
    raw = message.text.strip().replace(" ", "").replace(",", "")
    try:
        amount = Decimal(raw)
    except InvalidOperation:
        await message.answer("Noto'g'ri summa. Faqat raqam kiriting (masalan: 150000).")
        return
    if amount <= 0:
        await message.answer("Summa musbat bo'lishi kerak.")
        return

    data = await state.get_data()
    async with acquire() as conn:
        balance = await conn.fetchval(
            "SELECT balance_uzs FROM v_wallet_balances WHERE wallet_id = $1", data["source_id"]
        )
        fx_rate = Decimal("1")
        if data["currency"] != "UZS":
            fx_rate = await conn.fetchval(
                "SELECT rate_uzs FROM exchange_rates WHERE currency = $1 "
                "ORDER BY fetched_at DESC LIMIT 1",
                data["currency"],
            ) or Decimal("1")

    amount_uzs = (amount * fx_rate).quantize(Decimal("0.01"))
    if balance is not None and amount_uzs > balance:
        await message.answer(
            f"Kassada yetarli mablag' yo'q. Joriy balans: {balance} UZS, "
            f"so'ralgan: {amount_uzs} UZS."
        )
        return

    await state.update_data(amount=str(amount), fx_rate=str(fx_rate), amount_uzs=str(amount_uzs))
    await state.set_state(TransferFlow.entering_description)
    await message.answer('Izoh kiriting (kerak bo\'lmasa "-" yuboring):')


@router.message(TransferFlow.entering_description, F.text)
async def msg_description_entered(message: Message, state: FSMContext) -> None:
    description = None if message.text.strip() == "-" else message.text.strip()
    data = await state.get_data()
    await state.clear()

    group_id = uuid.uuid4()
    amount = Decimal(data["amount"])
    fx_rate = Decimal(data["fx_rate"])
    amount_uzs = Decimal(data["amount_uzs"])
    admin_id = data["admin_id"]
    currency = data["currency"]

    async with acquire(actor_id=admin_id) as conn:
        async with conn.transaction():
            await conn.execute(
                """INSERT INTO transactions
                   (kind, wallet_id, amount, currency, fx_rate, amount_uzs,
                    description, transfer_group_id, created_by)
                   VALUES ('transfer_out', $1, $2, $3::currency_code, $4, $5, $6, $7, $8)""",
                data["source_id"], amount, currency, fx_rate, amount_uzs,
                description, group_id, admin_id,
            )
            await conn.execute(
                """INSERT INTO transactions
                   (kind, wallet_id, amount, currency, fx_rate, amount_uzs,
                    description, transfer_group_id, created_by)
                   VALUES ('transfer_in', $1, $2, $3::currency_code, $4, $5, $6, $7, $8)""",
                data["dest_id"], amount, currency, fx_rate, amount_uzs,
                description, group_id, admin_id,
            )

    await message.answer(f"✅ Transfer bajarildi: {amount} {currency} (≈{amount_uzs} UZS)")
