"""Kirim (daromad) qo'shish — bosqichli FSM oqimi.

Oqim:  summa → daromad manbasi → kassa → fond → tasdiq → transactions(kind='income')
"""
from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.db import acquire
from app.handlers.common import fmt_money, get_current_user, parse_amount
from app.keyboards import BTN_INCOME, choices_kb, confirm_kb, main_menu_kb

router = Router()

PREFIX = "inc"  # callback_data prefiksi


class IncomeFSM(StatesGroup):
    amount = State()
    source = State()
    wallet = State()
    fund = State()
    confirm = State()


# --------------------------- 1. Boshlash: summa ---------------------------
@router.message(F.text == BTN_INCOME)
async def income_start(message: Message, state: FSMContext) -> None:
    user = await get_current_user(message.from_user.id)
    if not user:
        await message.answer("Avval /start orqali ro'yxatdan o'ting.")
        return
    await state.clear()
    await state.update_data(user_id=user["id"])
    await state.set_state(IncomeFSM.amount)
    await message.answer("➕ Kirim summasini kiriting (masalan: 1 500 000):")


@router.message(IncomeFSM.amount)
async def income_amount(message: Message, state: FSMContext) -> None:
    amount = parse_amount(message.text)
    if amount is None:
        await message.answer("❗️ Noto'g'ri summa. Musbat raqam kiriting (masalan: 250000):")
        return
    await state.update_data(amount=str(amount))
    async with acquire() as conn:
        # Smart tavsiya: ko'p ishlatilgan manbalar tepada
        sources = await conn.fetch(
            """SELECT s.id, s.name FROM income_sources s WHERE s.is_active
               ORDER BY (SELECT count(*) FROM transactions t
                         WHERE t.source_id = s.id AND t.kind = 'income') DESC, s.name"""
        )
    if not sources:
        await state.clear()
        await message.answer("Daromad manbalari topilmadi. Administrator bilan bog'laning.")
        return
    await state.set_state(IncomeFSM.source)
    await message.answer("Daromad manbasini tanlang:", reply_markup=choices_kb(sources, PREFIX + "_src"))


# --------------------------- 2. Daromad manbasi ---------------------------
@router.callback_query(IncomeFSM.source, F.data.startswith(PREFIX + "_src:"))
async def income_source(call: CallbackQuery, state: FSMContext) -> None:
    value = call.data.split(":", 1)[1]
    if value == "cancel":
        await _cancel(call, state)
        return
    async with acquire() as conn:
        src = await conn.fetchrow("SELECT id, name FROM income_sources WHERE id = $1", int(value))
        wallets = await conn.fetch(
            "SELECT id, name FROM wallets WHERE is_active ORDER BY name"
        )
    await state.update_data(source_id=src["id"], source_name=src["name"])
    await state.set_state(IncomeFSM.wallet)
    await call.message.edit_text(
        f"Manba: {src['name']}\n\nKassani tanlang:",
        reply_markup=choices_kb(wallets, PREFIX + "_wal"),
    )
    await call.answer()


# --------------------------- 3. Kassa ---------------------------
@router.callback_query(IncomeFSM.wallet, F.data.startswith(PREFIX + "_wal:"))
async def income_wallet(call: CallbackQuery, state: FSMContext) -> None:
    value = call.data.split(":", 1)[1]
    if value == "cancel":
        await _cancel(call, state)
        return
    async with acquire() as conn:
        wal = await conn.fetchrow(
            "SELECT id, name, currency FROM wallets WHERE id = $1", int(value)
        )
        funds = await conn.fetch("SELECT id, name FROM funds WHERE is_active ORDER BY name")
    await state.update_data(
        wallet_id=wal["id"], wallet_name=wal["name"], currency=wal["currency"]
    )
    await state.set_state(IncomeFSM.fund)
    await call.message.edit_text(
        f"Kassa: {wal['name']}\n\nFondni tanlang:",
        reply_markup=choices_kb(
            funds, PREFIX + "_fund", extra=[("➖ Fondsiz", PREFIX + "_fund:none")]
        ),
    )
    await call.answer()


# --------------------------- 4. Fond ---------------------------
@router.callback_query(IncomeFSM.fund, F.data.startswith(PREFIX + "_fund:"))
async def income_fund(call: CallbackQuery, state: FSMContext) -> None:
    value = call.data.split(":", 1)[1]
    if value == "cancel":
        await _cancel(call, state)
        return
    if value == "none":
        await state.update_data(fund_id=None, fund_name="—")
    else:
        async with acquire() as conn:
            fund = await conn.fetchrow("SELECT id, name FROM funds WHERE id = $1", int(value))
        await state.update_data(fund_id=fund["id"], fund_name=fund["name"])
    await state.set_state(IncomeFSM.confirm)
    data = await state.get_data()
    await call.message.edit_text(_summary(data), reply_markup=confirm_kb(PREFIX))
    await call.answer()


# --------------------------- 5. Tasdiq ---------------------------
@router.callback_query(IncomeFSM.confirm, F.data.startswith(PREFIX + ":"))
async def income_confirm(call: CallbackQuery, state: FSMContext) -> None:
    action = call.data.split(":", 1)[1]
    if action != "ok":
        await _cancel(call, state)
        return
    data = await state.get_data()
    amount = Decimal(data["amount"])
    user_id = data["user_id"]
    async with acquire(actor_id=user_id) as conn:
        await conn.execute(
            """INSERT INTO transactions
                   (kind, wallet_id, fund_id, amount, currency, fx_rate, amount_uzs,
                    source_id, created_by)
               VALUES ('income', $1, $2, $3, $4, 1, $3, $5, $6)""",
            data["wallet_id"],
            data["fund_id"],
            amount,
            data["currency"],
            data["source_id"],
            user_id,
        )
    await state.clear()
    await call.message.edit_text("✅ Kirim saqlandi.\n\n" + _summary(data))
    await call.message.answer("Asosiy menyu:", reply_markup=main_menu_kb())
    await call.answer("Saqlandi")


# --------------------------- yordamchilar ---------------------------
def _summary(data: dict) -> str:
    return (
        "🧾 <b>Kirimni tasdiqlang</b>\n\n"
        f"Summa: <b>{fmt_money(data['amount'], data['currency'])}</b>\n"
        f"Manba: {data['source_name']}\n"
        f"Kassa: {data['wallet_name']}\n"
        f"Fond: {data['fund_name']}"
    )


async def _cancel(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text("❌ Bekor qilindi.")
    await call.message.answer("Asosiy menyu:", reply_markup=main_menu_kb())
    await call.answer()
