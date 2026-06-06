"""Transfer — pulni manbadan maqsadga ko'chirish (kassa/fond).

Umumiy oqim manba (kassa, fond) → maqsad (kassa, fond) ni qamraydi, shu bilan:
  • kassa → kassa  (boshqa kassa tanlanadi)
  • fond  → fond   (bir kassa, boshqa fond)
  • kassa+fond     (ixtiyoriy manba/maqsad)

Har transfer ikki oyoqdan iborat: transfer_out (−) va transfer_in (+),
ikkalasi bir xil transfer_group_id (UUID) bilan bog'lanadi.
Multi-valyuta: UZS↔USD bo'lsa kurs (fx.get_rate) bilan, UZS qiymati saqlanadi.
"""
import uuid
from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.db import acquire
from app.handlers.common import fmt_money, get_current_user, parse_amount
from app.keyboards import BTN_TRANSFER, choices_kb, confirm_kb, main_menu_kb
from app.services import fx

router = Router()

PREFIX = "trf"


class TransferFSM(StatesGroup):
    src_wallet = State()
    src_fund = State()
    dst_wallet = State()
    dst_fund = State()
    amount = State()
    confirm = State()


# --------------------------- boshlash ---------------------------
@router.message(F.text == BTN_TRANSFER)
async def transfer_start(message: Message, state: FSMContext) -> None:
    user = await get_current_user(message.from_user.id)
    if not user:
        await message.answer("Avval /start orqali ro'yxatdan o'ting.")
        return
    await state.clear()
    await state.update_data(user_id=user["id"])
    async with acquire() as conn:
        wallets = await conn.fetch("SELECT id, name FROM wallets WHERE is_active ORDER BY name")
    await state.set_state(TransferFSM.src_wallet)
    await message.answer(
        "🔄 <b>Transfer</b>\n\nManba kassani tanlang:",
        reply_markup=choices_kb(wallets, PREFIX + "_sw"),
    )


@router.callback_query(TransferFSM.src_wallet, F.data.startswith(PREFIX + "_sw:"))
async def transfer_src_wallet(call: CallbackQuery, state: FSMContext) -> None:
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
        src_wallet_id=wal["id"], src_wallet_name=wal["name"], src_currency=wal["currency"]
    )
    await state.set_state(TransferFSM.src_fund)
    await call.message.edit_text(
        f"Manba kassa: {wal['name']}\n\nManba fondni tanlang:",
        reply_markup=choices_kb(funds, PREFIX + "_sf", extra=[("➖ Fondsiz", PREFIX + "_sf:none")]),
    )
    await call.answer()


@router.callback_query(TransferFSM.src_fund, F.data.startswith(PREFIX + "_sf:"))
async def transfer_src_fund(call: CallbackQuery, state: FSMContext) -> None:
    value = call.data.split(":", 1)[1]
    if value == "cancel":
        await _cancel(call, state)
        return
    await _set_fund(state, "src", value)
    async with acquire() as conn:
        wallets = await conn.fetch("SELECT id, name FROM wallets WHERE is_active ORDER BY name")
    await state.set_state(TransferFSM.dst_wallet)
    await call.message.edit_text(
        "Maqsad kassani tanlang:",
        reply_markup=choices_kb(wallets, PREFIX + "_dw"),
    )
    await call.answer()


@router.callback_query(TransferFSM.dst_wallet, F.data.startswith(PREFIX + "_dw:"))
async def transfer_dst_wallet(call: CallbackQuery, state: FSMContext) -> None:
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
        dst_wallet_id=wal["id"], dst_wallet_name=wal["name"], dst_currency=wal["currency"]
    )
    await state.set_state(TransferFSM.dst_fund)
    await call.message.edit_text(
        f"Maqsad kassa: {wal['name']}\n\nMaqsad fondni tanlang:",
        reply_markup=choices_kb(funds, PREFIX + "_df", extra=[("➖ Fondsiz", PREFIX + "_df:none")]),
    )
    await call.answer()


@router.callback_query(TransferFSM.dst_fund, F.data.startswith(PREFIX + "_df:"))
async def transfer_dst_fund(call: CallbackQuery, state: FSMContext) -> None:
    value = call.data.split(":", 1)[1]
    if value == "cancel":
        await _cancel(call, state)
        return
    await _set_fund(state, "dst", value)
    data = await state.get_data()
    # Manba va maqsad bir xil bo'lsa — transfer ma'nosiz
    if data["src_wallet_id"] == data["dst_wallet_id"] and data["src_fund_id"] == data["dst_fund_id"]:
        await state.clear()
        await call.message.edit_text(
            "❗️ Manba va maqsad bir xil. Transfer bekor qilindi."
        )
        await call.message.answer("Asosiy menyu:", reply_markup=main_menu_kb())
        await call.answer()
        return
    await state.set_state(TransferFSM.amount)
    await call.message.edit_text(
        f"Transfer summasini kiriting ({data['src_currency']} da):"
    )
    await call.answer()


@router.message(TransferFSM.amount)
async def transfer_amount(message: Message, state: FSMContext) -> None:
    amount = parse_amount(message.text)
    if amount is None:
        await message.answer("❗️ Noto'g'ri summa. Musbat raqam kiriting:")
        return
    data = await state.get_data()
    src_cur, dst_cur = data["src_currency"], data["dst_currency"]

    fx_src = await fx.get_rate(src_cur)
    amount_uzs = fx.to_uzs(amount, fx_src)
    if dst_cur == src_cur:
        fx_dst = fx_src
        dst_amount = amount
    else:
        fx_dst = await fx.get_rate(dst_cur)
        dst_amount = (amount_uzs / fx_dst).quantize(Decimal("0.01"))

    await state.update_data(
        amount=str(amount),
        fx_src=str(fx_src),
        amount_uzs=str(amount_uzs),
        dst_amount=str(dst_amount),
        fx_dst=str(fx_dst),
    )
    await state.set_state(TransferFSM.confirm)
    await message.answer(_summary(await state.get_data()), reply_markup=confirm_kb(PREFIX))


@router.callback_query(TransferFSM.confirm, F.data.startswith(PREFIX + ":"))
async def transfer_confirm(call: CallbackQuery, state: FSMContext) -> None:
    if call.data.split(":", 1)[1] != "ok":
        await _cancel(call, state)
        return
    data = await state.get_data()
    user_id = data["user_id"]
    group_id = uuid.uuid4()
    desc = f"Transfer: {data['src_wallet_name']} → {data['dst_wallet_name']}"

    async with acquire(actor_id=user_id) as conn:
        async with conn.transaction():
            # chiqish oyog'i (−)
            await conn.execute(
                """INSERT INTO transactions
                       (kind, wallet_id, fund_id, amount, currency, fx_rate, amount_uzs,
                        transfer_group_id, description, created_by)
                   VALUES ('transfer_out', $1, $2, $3, $4, $5, $6, $7, $8, $9)""",
                data["src_wallet_id"], data["src_fund_id"], Decimal(data["amount"]),
                data["src_currency"], Decimal(data["fx_src"]), Decimal(data["amount_uzs"]),
                group_id, desc, user_id,
            )
            # kirish oyog'i (+) — UZS qiymati saqlanadi
            await conn.execute(
                """INSERT INTO transactions
                       (kind, wallet_id, fund_id, amount, currency, fx_rate, amount_uzs,
                        transfer_group_id, description, created_by)
                   VALUES ('transfer_in', $1, $2, $3, $4, $5, $6, $7, $8, $9)""",
                data["dst_wallet_id"], data["dst_fund_id"], Decimal(data["dst_amount"]),
                data["dst_currency"], Decimal(data["fx_dst"]), Decimal(data["amount_uzs"]),
                group_id, desc, user_id,
            )
    await state.clear()
    await call.message.edit_text("✅ Transfer bajarildi.\n\n" + _summary(data))
    await call.message.answer("Asosiy menyu:", reply_markup=main_menu_kb())
    await call.answer("Bajarildi")


# --------------------------- yordamchilar ---------------------------
async def _set_fund(state: FSMContext, side: str, value: str) -> None:
    if value == "none":
        await state.update_data(**{f"{side}_fund_id": None, f"{side}_fund_name": "—"})
    else:
        async with acquire() as conn:
            fund = await conn.fetchrow("SELECT id, name FROM funds WHERE id = $1", int(value))
        await state.update_data(**{f"{side}_fund_id": fund["id"], f"{side}_fund_name": fund["name"]})


def _summary(data: dict) -> str:
    lines = [
        "🧾 <b>Transferni tasdiqlang</b>\n",
        f"Manba: {data['src_wallet_name']} / {data['src_fund_name']}",
        f"  − {fmt_money(data['amount'], data['src_currency'])}",
        f"Maqsad: {data['dst_wallet_name']} / {data['dst_fund_name']}",
        f"  + {fmt_money(data['dst_amount'], data['dst_currency'])}",
    ]
    if data["src_currency"] != data["dst_currency"]:
        lines.append(f"\nKurs: 1 {data['src_currency']} → ... (UZS orqali)")
        lines.append(f"UZS qiymati: {fmt_money(data['amount_uzs'], 'UZS')}")
    return "\n".join(lines)


async def _cancel(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text("❌ Bekor qilindi.")
    await call.message.answer("Asosiy menyu:", reply_markup=main_menu_kb())
    await call.answer()
