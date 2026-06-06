"""Qarz moduli — berish/olish, qaytarish, muddat, hisobot.

Model:
  • lent      = qarz BERDIM  → kassadan chiqdi → transactions.kind='debt_out'
  • borrowed  = qarz OLDIM   → kassaga kirdi   → transactions.kind='debt_in'
  Qaytarish:
  • lent qaytib keldi   → kassaga kirdi  → 'debt_in'
  • borrowed ni qaytardim→ kassadan chiqdi→ 'debt_repay_out'
  Qoldiq: v_debt_outstanding;  holat: open/partial/paid/overdue (avtomatik).
"""
from datetime import date
from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.db import acquire
from app.handlers.common import fmt_date, fmt_money, get_current_user, parse_amount, parse_date
from app.keyboards import BTN_DEBT, choices_kb, confirm_kb, main_menu_kb
from app.services import fx

router = Router()

_SKIP_WORDS = {"yo'q", "yoq", "-", "skip", "o'tkazish", "otkazish", "yoʻq"}
DIR_LABEL = {"lent": "📤 Qarz berdim", "borrowed": "📥 Qarz oldim"}
STATUS_LABEL = {
    "open": "ochiq",
    "partial": "qisman",
    "paid": "to'langan",
    "overdue": "muddati o'tgan",
    "written_off": "o'chirilgan",
}


# =====================================================================
#  QARZ SUBMENYUSI
# =====================================================================
def _debt_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📤 Qarz berdim", callback_data="debt_menu:lent")],
            [InlineKeyboardButton(text="📥 Qarz oldim", callback_data="debt_menu:borrowed")],
            [InlineKeyboardButton(text="📋 Faol qarzlar", callback_data="debt_menu:list")],
            [InlineKeyboardButton(text="💵 Qaytarish", callback_data="debt_menu:repay")],
            [InlineKeyboardButton(text="📅 Muddat uzaytirish", callback_data="debt_menu:extend")],
            [InlineKeyboardButton(text="❌ Yopish", callback_data="debt_menu:cancel")],
        ]
    )


@router.message(F.text == BTN_DEBT)
async def debt_entry(message: Message, state: FSMContext) -> None:
    user = await get_current_user(message.from_user.id)
    if not user:
        await message.answer("Avval /start orqali ro'yxatdan o'ting.")
        return
    await state.clear()
    await state.update_data(user_id=user["id"])
    await message.answer("💳 <b>Qarz</b> — amални tanlang:", reply_markup=_debt_menu_kb())


@router.callback_query(F.data.startswith("debt_menu:"))
async def debt_menu(call: CallbackQuery, state: FSMContext) -> None:
    action = call.data.split(":", 1)[1]
    if action == "cancel":
        await call.message.edit_text("Yopildi.")
        await call.answer()
        return
    if action in ("lent", "borrowed"):
        await state.update_data(direction=action)
        await state.set_state(NewDebtFSM.amount)
        await call.message.edit_text(
            f"{DIR_LABEL[action]}\n\nQarz summasini kiriting:"
        )
    elif action == "list":
        await _show_active(call.message)
    elif action == "repay":
        await _start_repay(call, state)
    elif action == "extend":
        await _start_extend(call, state)
    await call.answer()


# =====================================================================
#  YANGI QARZ
# =====================================================================
class NewDebtFSM(StatesGroup):
    amount = State()
    counterparty = State()
    phone = State()
    wallet = State()
    fund = State()
    due = State()
    confirm = State()


@router.message(NewDebtFSM.amount)
async def newdebt_amount(message: Message, state: FSMContext) -> None:
    amount = parse_amount(message.text)
    if amount is None:
        await message.answer("❗️ Noto'g'ri summa. Musbat raqam kiriting:")
        return
    await state.update_data(amount=str(amount))
    await state.set_state(NewDebtFSM.counterparty)
    await message.answer("Kontragent (kim) ismini kiriting:")


@router.message(NewDebtFSM.counterparty)
async def newdebt_counterparty(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer("❗️ Ism bo'sh bo'lmasin. Qaytadan kiriting:")
        return
    await state.update_data(counterparty=name)
    await state.set_state(NewDebtFSM.phone)
    await message.answer("Telefon raqamini kiriting (yoki «yo'q»):")


@router.message(NewDebtFSM.phone)
async def newdebt_phone(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    phone = None if raw.lower() in _SKIP_WORDS else raw
    await state.update_data(phone=phone)
    async with acquire() as conn:
        wallets = await conn.fetch("SELECT id, name FROM wallets WHERE is_active ORDER BY name")
    await state.set_state(NewDebtFSM.wallet)
    await message.answer("Kassani tanlang:", reply_markup=choices_kb(wallets, "debt_w"))


@router.callback_query(NewDebtFSM.wallet, F.data.startswith("debt_w:"))
async def newdebt_wallet(call: CallbackQuery, state: FSMContext) -> None:
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
    await state.set_state(NewDebtFSM.fund)
    await call.message.edit_text(
        f"Kassa: {wal['name']}\n\nFondni tanlang:",
        reply_markup=choices_kb(funds, "debt_f", extra=[("➖ Fondsiz", "debt_f:none")]),
    )
    await call.answer()


@router.callback_query(NewDebtFSM.fund, F.data.startswith("debt_f:"))
async def newdebt_fund(call: CallbackQuery, state: FSMContext) -> None:
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
    await state.set_state(NewDebtFSM.due)
    await call.message.edit_text(
        "Qaytarish muddatini kiriting (masalan 30.06.2026) yoki «yo'q»:"
    )
    await call.answer()


@router.message(NewDebtFSM.due)
async def newdebt_due(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if raw.lower() in _SKIP_WORDS:
        due = None
    else:
        due = parse_date(raw)
        if due is None:
            await message.answer("❗️ Sanani 30.06.2026 ko'rinishida kiriting yoki «yo'q»:")
            return
    await state.update_data(due=due.isoformat() if due else None)
    await state.set_state(NewDebtFSM.confirm)
    await message.answer(_newdebt_summary(await state.get_data()), reply_markup=confirm_kb("debt_new"))


@router.callback_query(NewDebtFSM.confirm, F.data.startswith("debt_new:"))
async def newdebt_confirm(call: CallbackQuery, state: FSMContext) -> None:
    if call.data.split(":", 1)[1] != "ok":
        await _cancel(call, state)
        return
    data = await state.get_data()
    user_id = data["user_id"]
    direction = data["direction"]
    currency = data["currency"]
    amount = Decimal(data["amount"])
    fx_rate = await fx.get_rate(currency)
    amount_uzs = fx.to_uzs(amount, fx_rate)
    due = date.fromisoformat(data["due"]) if data["due"] else None
    kind = "debt_out" if direction == "lent" else "debt_in"

    async with acquire(actor_id=user_id) as conn:
        async with conn.transaction():
            debt_id = await conn.fetchval(
                """INSERT INTO debts
                       (direction, counterparty_name, counterparty_phone, principal, currency,
                        wallet_id, fund_id, due_date, created_by)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING id""",
                direction, data["counterparty"], data["phone"], amount, currency,
                data["wallet_id"], data["fund_id"], due, user_id,
            )
            await conn.execute(
                """INSERT INTO transactions
                       (kind, wallet_id, fund_id, amount, currency, fx_rate, amount_uzs,
                        debt_id, description, created_by)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
                kind, data["wallet_id"], data["fund_id"], amount, currency, fx_rate,
                amount_uzs, debt_id, f"Qarz ({DIR_LABEL[direction]}): {data['counterparty']}",
                user_id,
            )
            if due is not None:
                await conn.execute(
                    "INSERT INTO debt_reminders (debt_id, remind_at) VALUES ($1, ($2::date + TIME '09:00'))",
                    debt_id, due,
                )
            await _refresh_status(conn, debt_id)

    await state.clear()
    await call.message.edit_text("✅ Qarz saqlandi.\n\n" + _newdebt_summary(data))
    await call.message.answer("Asosiy menyu:", reply_markup=main_menu_kb())
    await call.answer("Saqlandi")


# =====================================================================
#  QAYTARISH
# =====================================================================
class RepayFSM(StatesGroup):
    pick = State()
    amount = State()
    confirm = State()


async def _start_repay(call: CallbackQuery, state: FSMContext) -> None:
    debts = await _fetch_active()
    if not debts:
        await call.message.edit_text("Faol qarzlar yo'q.")
        return
    rows = [
        [InlineKeyboardButton(
            text=f"{DIR_LABEL[d['direction']]} · {d['counterparty_name']} · "
                 f"{fmt_money(d['remaining'], d['currency'])}",
            callback_data=f"debt_pay:{d['debt_id']}",
        )]
        for d in debts
    ]
    rows.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="debt_pay:cancel")])
    await state.set_state(RepayFSM.pick)
    await call.message.edit_text(
        "Qaysi qarz qaytarilsin?", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )


@router.callback_query(RepayFSM.pick, F.data.startswith("debt_pay:"))
async def repay_pick(call: CallbackQuery, state: FSMContext) -> None:
    value = call.data.split(":", 1)[1]
    if value == "cancel":
        await _cancel(call, state)
        return
    async with acquire() as conn:
        d = await conn.fetchrow(
            """SELECT o.debt_id, o.direction, o.counterparty_name, o.currency, o.remaining,
                      dd.wallet_id, dd.fund_id
               FROM v_debt_outstanding o JOIN debts dd ON dd.id = o.debt_id
               WHERE o.debt_id = $1""",
            int(value),
        )
    await state.update_data(
        debt_id=d["debt_id"], direction=d["direction"], currency=d["currency"],
        remaining=str(d["remaining"]), wallet_id=d["wallet_id"], fund_id=d["fund_id"],
        counterparty=d["counterparty_name"],
    )
    await state.set_state(RepayFSM.amount)
    await call.message.edit_text(
        f"{d['counterparty_name']} — qoldiq: <b>{fmt_money(d['remaining'], d['currency'])}</b>\n\n"
        "Qaytariladigan summani kiriting:"
    )
    await call.answer()


@router.message(RepayFSM.amount)
async def repay_amount(message: Message, state: FSMContext) -> None:
    amount = parse_amount(message.text)
    data = await state.get_data()
    if amount is None:
        await message.answer("❗️ Noto'g'ri summa. Musbat raqam kiriting:")
        return
    remaining = Decimal(data["remaining"])
    if amount > remaining:
        await message.answer(
            f"❗️ Qoldiqdan ({fmt_money(remaining, data['currency'])}) ko'p. Qaytadan kiriting:"
        )
        return
    await state.update_data(amount=str(amount))
    await state.set_state(RepayFSM.confirm)
    new_remaining = remaining - amount
    await message.answer(
        "🧾 <b>Qaytarishni tasdiqlang</b>\n\n"
        f"Kontragent: {data['counterparty']}\n"
        f"Summa: <b>{fmt_money(amount, data['currency'])}</b>\n"
        f"Yangi qoldiq: {fmt_money(new_remaining, data['currency'])}",
        reply_markup=confirm_kb("debt_rep"),
    )


@router.callback_query(RepayFSM.confirm, F.data.startswith("debt_rep:"))
async def repay_confirm(call: CallbackQuery, state: FSMContext) -> None:
    if call.data.split(":", 1)[1] != "ok":
        await _cancel(call, state)
        return
    data = await state.get_data()
    user_id = data["user_id"]
    currency = data["currency"]
    amount = Decimal(data["amount"])
    fx_rate = await fx.get_rate(currency)
    amount_uzs = fx.to_uzs(amount, fx_rate)
    # lent qaytib keldi → kassaga kirdi; borrowed ni qaytardim → kassadan chiqdi
    kind = "debt_in" if data["direction"] == "lent" else "debt_repay_out"

    async with acquire(actor_id=user_id) as conn:
        async with conn.transaction():
            txn_id = await conn.fetchval(
                """INSERT INTO transactions
                       (kind, wallet_id, fund_id, amount, currency, fx_rate, amount_uzs,
                        debt_id, description, created_by)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) RETURNING id""",
                kind, data["wallet_id"], data["fund_id"], amount, currency, fx_rate,
                amount_uzs, data["debt_id"], f"Qarz qaytarish: {data['counterparty']}", user_id,
            )
            await conn.execute(
                """INSERT INTO debt_payments
                       (debt_id, amount, currency, fx_rate, transaction_id, created_by)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                data["debt_id"], amount, currency, fx_rate, txn_id, user_id,
            )
            status = await _refresh_status(conn, data["debt_id"])

    await state.clear()
    await call.message.edit_text(
        f"✅ Qaytarish saqlandi. Holat: <b>{STATUS_LABEL.get(status, status)}</b>."
    )
    await call.message.answer("Asosiy menyu:", reply_markup=main_menu_kb())
    await call.answer("Saqlandi")


# =====================================================================
#  MUDDAT UZAYTIRISH
# =====================================================================
class ExtendFSM(StatesGroup):
    pick = State()
    new_date = State()


async def _start_extend(call: CallbackQuery, state: FSMContext) -> None:
    debts = await _fetch_active()
    if not debts:
        await call.message.edit_text("Faol qarzlar yo'q.")
        return
    rows = [
        [InlineKeyboardButton(
            text=f"{d['counterparty_name']} · muddat: {fmt_date(d['due_date'])}",
            callback_data=f"debt_ext:{d['debt_id']}",
        )]
        for d in debts
    ]
    rows.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="debt_ext:cancel")])
    await state.set_state(ExtendFSM.pick)
    await call.message.edit_text(
        "Qaysi qarz muddati uzaytirilsin?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(ExtendFSM.pick, F.data.startswith("debt_ext:"))
async def extend_pick(call: CallbackQuery, state: FSMContext) -> None:
    value = call.data.split(":", 1)[1]
    if value == "cancel":
        await _cancel(call, state)
        return
    await state.update_data(debt_id=int(value))
    await state.set_state(ExtendFSM.new_date)
    await call.message.edit_text("Yangi muddatni kiriting (masalan 31.12.2026):")
    await call.answer()


@router.message(ExtendFSM.new_date)
async def extend_apply(message: Message, state: FSMContext) -> None:
    due = parse_date((message.text or "").strip())
    if due is None:
        await message.answer("❗️ Sanani 31.12.2026 ko'rinishida kiriting:")
        return
    data = await state.get_data()
    async with acquire(actor_id=data["user_id"]) as conn:
        async with conn.transaction():
            await conn.execute("UPDATE debts SET due_date = $2 WHERE id = $1", data["debt_id"], due)
            # eski yuborilmagan eslatmani yangilaymiz (yoki yangisini qo'shamiz)
            await conn.execute(
                "DELETE FROM debt_reminders WHERE debt_id = $1 AND is_sent = FALSE", data["debt_id"]
            )
            await conn.execute(
                "INSERT INTO debt_reminders (debt_id, remind_at) VALUES ($1, ($2::date + TIME '09:00'))",
                data["debt_id"], due,
            )
            await _refresh_status(conn, data["debt_id"])
    await state.clear()
    await message.answer(
        f"✅ Muddat yangilandi: <b>{fmt_date(due)}</b>.", reply_markup=main_menu_kb()
    )


# =====================================================================
#  HISOBOT: FAOL QARZLAR
# =====================================================================
async def _show_active(message: Message) -> None:
    debts = await _fetch_active()
    if not debts:
        await message.edit_text("Faol qarzlar yo'q. ✅")
        return
    today = date.today()
    lent_lines, borrowed_lines = [], []
    for d in debts:
        mark = ""
        if d["due_date"] is not None:
            if d["due_date"] < today:
                mark = " ⛔️"  # muddati o'tgan
            elif d["due_date"] == today:
                mark = " ⏰"  # bugun
        line = (
            f"• {d['counterparty_name']}: <b>{fmt_money(d['remaining'], d['currency'])}</b> "
            f"(muddat: {fmt_date(d['due_date'])}, {STATUS_LABEL.get(d['status'], d['status'])}){mark}"
        )
        if d["direction"] == "lent":
            lent_lines.append(line)
        else:
            borrowed_lines.append(line)

    parts = ["📋 <b>Faol qarzlar</b>"]
    parts.append("\n📥 <b>Menga qarzdor</b> (men berdim):")
    parts.extend(lent_lines or ["  —"])
    parts.append("\n📤 <b>Men qaytarishim kerak</b> (men oldim):")
    parts.extend(borrowed_lines or ["  —"])
    await message.edit_text("\n".join(parts))


# =====================================================================
#  YORDAMCHILAR
# =====================================================================
async def _fetch_active() -> list:
    """Qoldig'i bor (faol) qarzlar — repay/extend/hisobot uchun."""
    async with acquire() as conn:
        return await conn.fetch(
            """SELECT o.debt_id, o.direction, o.counterparty_name, o.currency,
                      o.remaining, o.due_date, o.status
               FROM v_debt_outstanding o
               WHERE o.remaining > 0 AND o.status <> 'written_off'
               ORDER BY o.due_date NULLS LAST, o.debt_id"""
        )


async def _refresh_status(conn, debt_id: int) -> str:
    """To'lovlar va muddatga qarab debts.status ni qayta hisoblaydi."""
    row = await conn.fetchrow(
        """SELECT d.principal, d.due_date, COALESCE(SUM(p.amount), 0) AS paid
           FROM debts d LEFT JOIN debt_payments p ON p.debt_id = d.id
           WHERE d.id = $1 GROUP BY d.id""",
        debt_id,
    )
    paid = Decimal(row["paid"])
    principal = Decimal(row["principal"])
    if paid >= principal:
        status = "paid"
    elif paid > 0:
        status = "partial"
    else:
        status = "open"
    if status != "paid" and row["due_date"] is not None and row["due_date"] < date.today():
        status = "overdue"
    await conn.execute("UPDATE debts SET status = $2 WHERE id = $1", debt_id, status)
    return status


def _newdebt_summary(data: dict) -> str:
    return (
        f"🧾 <b>Qarzni tasdiqlang</b> — {DIR_LABEL[data['direction']]}\n\n"
        f"Summa: <b>{fmt_money(data['amount'], data['currency'])}</b>\n"
        f"Kontragent: {data['counterparty']}\n"
        f"Telefon: {data['phone'] or '—'}\n"
        f"Kassa: {data['wallet_name']}\n"
        f"Fond: {data['fund_name']}\n"
        f"Muddat: {fmt_date(date.fromisoformat(data['due']) if data['due'] else None)}"
    )


async def _cancel(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text("❌ Bekor qilindi.")
    await call.message.answer("Asosiy menyu:", reply_markup=main_menu_kb())
    await call.answer()
