"""Balanslarni ko'rsatish + boshlang'ich balans kiritish.

- Balanslar: v_wallet_balances va v_fund_balances view'laridan o'qiladi.
- Boshlang'ich balans oqimi:  summa → kassa → fond → tasdiq → transactions(kind='opening')
"""
from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.db import acquire
from app.handlers.common import fmt_money, get_current_user, parse_amount
from app.keyboards import BTN_BALANCES, BTN_OPENING, choices_kb, confirm_kb, main_menu_kb

router = Router()

PREFIX = "opn"  # boshlang'ich balans callback prefiksi


# =====================================================================
#  BALANSLARNI KO'RSATISH
# =====================================================================
@router.message(F.text == BTN_BALANCES)
async def show_balances(message: Message) -> None:
    user = await get_current_user(message.from_user.id)
    if not user:
        await message.answer("Avval /start orqali ro'yxatdan o'ting.")
        return
    async with acquire() as conn:
        wallets = await conn.fetch(
            "SELECT name, currency, balance_uzs FROM v_wallet_balances ORDER BY name"
        )
        funds = await conn.fetch(
            "SELECT name, balance_uzs FROM v_fund_balances ORDER BY name"
        )

    lines = ["📊 <b>Kassa balanslari</b>"]
    total = Decimal(0)
    for w in wallets:
        lines.append(f"• {w['name']}: <b>{fmt_money(w['balance_uzs'], 'UZS')}</b>")
        total += Decimal(w["balance_uzs"])
    lines.append(f"\n💰 Jami (UZS): <b>{fmt_money(total, 'UZS')}</b>")

    lines.append("\n🗂 <b>Fond balanslari</b>")
    for f in funds:
        lines.append(f"• {f['name']}: <b>{fmt_money(f['balance_uzs'], 'UZS')}</b>")

    await message.answer("\n".join(lines), reply_markup=main_menu_kb())


# =====================================================================
#  BOSHLANG'ICH BALANS (kind='opening')
# =====================================================================
class OpeningFSM(StatesGroup):
    amount = State()
    wallet = State()
    fund = State()
    confirm = State()


@router.message(F.text == BTN_OPENING)
async def opening_start(message: Message, state: FSMContext) -> None:
    user = await get_current_user(message.from_user.id)
    if not user:
        await message.answer("Avval /start orqali ro'yxatdan o'ting.")
        return
    await state.clear()
    await state.update_data(user_id=user["id"])
    await state.set_state(OpeningFSM.amount)
    await message.answer("🏦 Boshlang'ich balans summasini kiriting:")


@router.message(OpeningFSM.amount)
async def opening_amount(message: Message, state: FSMContext) -> None:
    amount = parse_amount(message.text)
    if amount is None:
        await message.answer("❗️ Noto'g'ri summa. Musbat raqam kiriting:")
        return
    await state.update_data(amount=str(amount))
    async with acquire() as conn:
        wallets = await conn.fetch("SELECT id, name FROM wallets WHERE is_active ORDER BY name")
    await state.set_state(OpeningFSM.wallet)
    await message.answer("Kassani tanlang:", reply_markup=choices_kb(wallets, PREFIX + "_wal"))


@router.callback_query(OpeningFSM.wallet, F.data.startswith(PREFIX + "_wal:"))
async def opening_wallet(call: CallbackQuery, state: FSMContext) -> None:
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
    await state.set_state(OpeningFSM.fund)
    await call.message.edit_text(
        f"Kassa: {wal['name']}\n\nFondni tanlang:",
        reply_markup=choices_kb(
            funds, PREFIX + "_fund", extra=[("➖ Fondsiz", PREFIX + "_fund:none")]
        ),
    )
    await call.answer()


@router.callback_query(OpeningFSM.fund, F.data.startswith(PREFIX + "_fund:"))
async def opening_fund(call: CallbackQuery, state: FSMContext) -> None:
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
    await state.set_state(OpeningFSM.confirm)
    data = await state.get_data()
    await call.message.edit_text(_summary(data), reply_markup=confirm_kb(PREFIX))
    await call.answer()


@router.callback_query(OpeningFSM.confirm, F.data.startswith(PREFIX + ":"))
async def opening_confirm(call: CallbackQuery, state: FSMContext) -> None:
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
                   (kind, wallet_id, fund_id, amount, currency, fx_rate, amount_uzs, created_by)
               VALUES ('opening', $1, $2, $3, $4, 1, $3, $5)""",
            data["wallet_id"],
            data["fund_id"],
            amount,
            data["currency"],
            user_id,
        )
    await state.clear()
    await call.message.edit_text("✅ Boshlang'ich balans saqlandi.\n\n" + _summary(data))
    await call.message.answer("Asosiy menyu:", reply_markup=main_menu_kb())
    await call.answer("Saqlandi")


# --------------------------- yordamchilar ---------------------------
def _summary(data: dict) -> str:
    return (
        "🧾 <b>Boshlang'ich balansni tasdiqlang</b>\n\n"
        f"Summa: <b>{fmt_money(data['amount'], data['currency'])}</b>\n"
        f"Kassa: {data['wallet_name']}\n"
        f"Fond: {data['fund_name']}"
    )


async def _cancel(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text("❌ Bekor qilindi.")
    await call.message.answer("Asosiy menyu:", reply_markup=main_menu_kb())
    await call.answer()
