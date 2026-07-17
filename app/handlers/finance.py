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

CAN_RECORD_ROLES = {"admin", "manager"}
KIND_LABEL = {"income": "Kirim", "expense": "Chiqim"}


class RecordTxn(StatesGroup):
    choosing_wallet = State()
    choosing_category = State()
    entering_amount = State()
    entering_description = State()


async def _get_user(conn, telegram_id: int):
    return await conn.fetchrow(
        "SELECT id, role, full_name FROM users WHERE telegram_id = $1 AND is_active",
        telegram_id,
    )


def _cancel_row() -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="txcancel")]


def _wallets_kb(wallets) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"{w['name']} ({w['currency']})", callback_data=f"txw:{w['id']}")]
        for w in wallets
    ]
    rows.append(_cancel_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _categories_kb(items) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=item["name"], callback_data=f"txc:{item['id']}")] for item in items]
    rows.append(_cancel_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _start_record(message: Message, state: FSMContext, kind: str) -> None:
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

    if not wallets:
        await message.answer("Faol kassa topilmadi. Avval kassa qo'shing.")
        return

    await state.clear()
    await state.set_state(RecordTxn.choosing_wallet)
    await state.update_data(kind=kind, user_id=user["id"])
    await message.answer(
        f"{KIND_LABEL[kind]} — qaysi kassaga?", reply_markup=_wallets_kb(wallets)
    )


@router.message(Command("kirim"))
async def cmd_income(message: Message, state: FSMContext) -> None:
    await _start_record(message, state, "income")


@router.message(Command("chiqim"))
async def cmd_expense(message: Message, state: FSMContext) -> None:
    await _start_record(message, state, "expense")


@router.message(Command("bekor"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer("Bekor qilinadigan amal yo'q.")
        return
    await state.clear()
    await message.answer("Bekor qilindi.")


@router.callback_query(F.data == "txcancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Bekor qilindi.")
    await callback.answer()


@router.callback_query(RecordTxn.choosing_wallet, F.data.startswith("txw:"))
async def cb_wallet_chosen(callback: CallbackQuery, state: FSMContext) -> None:
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
            rate_row = await conn.fetchrow(
                "SELECT rate_uzs FROM exchange_rates WHERE currency = $1 "
                "ORDER BY fetched_at DESC LIMIT 1",
                wallet["currency"],
            )
        if rate_row is None:
            await callback.message.edit_text(
                f"{wallet['currency']} uchun valyuta kursi hali kiritilmagan.\n"
                "Avval kursni qo'shing, keyin qayta urinib ko'ring."
            )
            await state.clear()
            await callback.answer()
            return
        fx_rate = rate_row["rate_uzs"]

    await state.update_data(
        wallet_id=wallet["id"], currency=wallet["currency"], fx_rate=str(fx_rate)
    )

    data = await state.get_data()
    kind = data["kind"]
    async with acquire() as conn:
        if kind == "income":
            items = await conn.fetch(
                "SELECT id, name FROM income_sources WHERE is_active ORDER BY id"
            )
        else:
            items = await conn.fetch(
                "SELECT id, name FROM expense_categories WHERE is_active ORDER BY id"
            )

    if not items:
        label = "manba" if kind == "income" else "kategoriya"
        await callback.message.edit_text(f"Faol {label} topilmadi.")
        await state.clear()
        await callback.answer()
        return

    await state.set_state(RecordTxn.choosing_category)
    label = "Manba" if kind == "income" else "Kategoriya"
    await callback.message.edit_text(f"{label} tanlang:", reply_markup=_categories_kb(items))
    await callback.answer()


@router.callback_query(RecordTxn.choosing_category, F.data.startswith("txc:"))
async def cb_category_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    item_id = int(callback.data.split(":", 1)[1])
    await state.update_data(category_id=item_id)
    await state.set_state(RecordTxn.entering_amount)
    await callback.message.edit_text("Summani kiriting (masalan: 150000):")
    await callback.answer()


@router.message(RecordTxn.entering_amount, F.text)
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

    await state.update_data(amount=str(amount))
    await state.set_state(RecordTxn.entering_description)
    await message.answer('Izoh kiriting (kerak bo\'lmasa "-" yuboring):')


@router.message(RecordTxn.entering_description, F.text)
async def msg_description_entered(message: Message, state: FSMContext) -> None:
    description = None if message.text.strip() == "-" else message.text.strip()
    data = await state.get_data()
    await state.clear()

    kind = data["kind"]
    wallet_id = data["wallet_id"]
    category_id = data["category_id"]
    amount = Decimal(data["amount"])
    fx_rate = Decimal(data["fx_rate"])
    amount_uzs = (amount * fx_rate).quantize(Decimal("0.01"))
    user_id = data["user_id"]

    txn_kind = "income" if kind == "income" else "expense"
    source_id = category_id if kind == "income" else None
    category_col_id = category_id if kind == "expense" else None

    async with acquire(actor_id=user_id) as conn:
        await conn.execute(
            """INSERT INTO transactions
               (kind, wallet_id, amount, currency, fx_rate, amount_uzs,
                source_id, category_id, description, created_by)
               VALUES ($1::txn_kind, $2, $3, $4::currency_code, $5, $6, $7, $8, $9, $10)""",
            txn_kind,
            wallet_id,
            amount,
            data["currency"],
            fx_rate,
            amount_uzs,
            source_id,
            category_col_id,
            description,
            user_id,
        )

    await message.answer(
        f"✅ {KIND_LABEL[kind]} qayd etildi: {amount} {data['currency']} (≈{amount_uzs} UZS)"
    )


@router.message(Command("balans"))
async def cmd_balance(message: Message) -> None:
    async with acquire() as conn:
        user = await _get_user(conn, message.from_user.id)
        if user is None:
            await message.answer("Avval ro'yxatdan o'ting: /start")
            return
        wallets = await conn.fetch(
            "SELECT name, currency, balance_uzs FROM v_wallet_balances ORDER BY name"
        )
        funds = await conn.fetch(
            "SELECT name, balance_uzs FROM v_fund_balances ORDER BY name"
        )

    lines = ["💰 <b>Kassalar balansi</b>"]
    for w in wallets:
        lines.append(f"• {w['name']} ({w['currency']}): {w['balance_uzs']:,} UZS".replace(",", " "))
    if funds:
        lines.append("\n🏦 <b>Fondlar balansi</b>")
        for f in funds:
            lines.append(f"• {f['name']}: {f['balance_uzs']:,} UZS".replace(",", " "))
    await message.answer("\n".join(lines), parse_mode="HTML")
