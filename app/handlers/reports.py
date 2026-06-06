"""Hisobotlar: P&L, balanslar, qarz, transfer tarixi + Excel/PDF eksport + Dashboard.

Matnli hisobotlar tezkor ko'rish uchun; Excel (openpyxl) va PDF (weasyprint) fayl
sifatida yuboriladi; Dashboard — Telegram Web App (WEBAPP_URL o'rnatilgan bo'lsa).
"""
import logging
from decimal import Decimal

from aiogram import F, Router
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)

from app.config import config
from app.db import acquire
from app.handlers.common import fmt_date, fmt_money, get_current_user
from app.keyboards import BTN_REPORTS, main_menu_kb
from app.services import export

router = Router()
log = logging.getLogger("imed-finance-bot.reports")


def _reports_menu_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="📊 P&L (oylik)", callback_data="rep:pnl")],
        [InlineKeyboardButton(text="💼 Balanslar", callback_data="rep:bal")],
        [InlineKeyboardButton(text="💳 Qarz hisoboti", callback_data="rep:debt")],
        [InlineKeyboardButton(text="🔄 Transfer tarixi", callback_data="rep:trf")],
        [
            InlineKeyboardButton(text="📥 Excel", callback_data="rep:excel"),
            InlineKeyboardButton(text="📄 PDF", callback_data="rep:pdf"),
        ],
    ]
    if config.webapp_url:
        rows.append(
            [InlineKeyboardButton(text="📈 Dashboard", web_app=WebAppInfo(url=config.webapp_url))]
        )
    rows.append([InlineKeyboardButton(text="❌ Yopish", callback_data="rep:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(F.text == BTN_REPORTS)
async def reports_entry(message: Message) -> None:
    user = await get_current_user(message.from_user.id)
    if not user:
        await message.answer("Avval /start orqali ro'yxatdan o'ting.")
        return
    await message.answer("📈 <b>Hisobotlar</b> — turini tanlang:", reply_markup=_reports_menu_kb())


@router.callback_query(F.data.startswith("rep:"))
async def reports_action(call: CallbackQuery) -> None:
    action = call.data.split(":", 1)[1]
    if action == "cancel":
        await call.message.edit_text("Yopildi.")
        await call.answer()
        return
    if action == "pnl":
        await call.message.edit_text(await _pnl_text(), reply_markup=_reports_menu_kb())
    elif action == "bal":
        await call.message.edit_text(await _balances_text(), reply_markup=_reports_menu_kb())
    elif action == "debt":
        await call.message.edit_text(await _debt_text(), reply_markup=_reports_menu_kb())
    elif action == "trf":
        await call.message.edit_text(await _transfers_text(), reply_markup=_reports_menu_kb())
    elif action == "excel":
        await call.answer("Excel tayyorlanmoqda...")
        data = await export.build_excel()
        await call.message.answer_document(
            BufferedInputFile(data, filename="hisobot.xlsx"), caption="📥 Excel hisobot"
        )
        await call.answer()
        return
    elif action == "pdf":
        await call.answer("PDF tayyorlanmoqda...")
        try:
            data = await export.build_pdf()
        except RuntimeError as exc:
            await call.message.answer(f"⚠️ {exc}")
            await call.answer()
            return
        await call.message.answer_document(
            BufferedInputFile(data, filename="hisobot.pdf"), caption="📄 PDF hisobot"
        )
        await call.answer()
        return
    await call.answer()


# --------------------------- matnli hisobotlar ---------------------------
async def _pnl_text() -> str:
    async with acquire() as conn:
        rows = await conn.fetch(
            """SELECT to_char(date_trunc('month', occurred_at), 'YYYY-MM') AS month,
                      COALESCE(SUM(amount_uzs) FILTER (WHERE kind = 'income'), 0) AS income,
                      COALESCE(SUM(amount_uzs) FILTER (WHERE kind = 'expense'), 0) AS expense
               FROM transactions
               WHERE kind IN ('income', 'expense')
               GROUP BY 1 ORDER BY 1 DESC LIMIT 6"""
        )
    if not rows:
        return "📊 <b>P&L</b>\n\nMa'lumot yo'q."
    lines = ["📊 <b>Oylik P&L</b> (so'nggi 6 oy)\n"]
    for r in rows:
        net = Decimal(r["income"]) - Decimal(r["expense"])
        sign = "🟢" if net >= 0 else "🔴"
        lines.append(
            f"<b>{r['month']}</b> {sign}\n"
            f"  Daromad: {fmt_money(r['income'], 'UZS')}\n"
            f"  Xarajat: {fmt_money(r['expense'], 'UZS')}\n"
            f"  Sof: {fmt_money(net, 'UZS')}"
        )
    return "\n".join(lines)


async def _balances_text() -> str:
    async with acquire() as conn:
        wallets = await conn.fetch(
            "SELECT name, currency, balance_uzs FROM v_wallet_balances ORDER BY name"
        )
        funds = await conn.fetch("SELECT name, balance_uzs FROM v_fund_balances ORDER BY name")
    lines = ["💼 <b>Balanslar</b>\n", "<b>Kassalar:</b>"]
    total = Decimal(0)
    for w in wallets:
        lines.append(f"• {w['name']}: {fmt_money(w['balance_uzs'], 'UZS')}")
        total += Decimal(w["balance_uzs"])
    lines.append(f"Jami: <b>{fmt_money(total, 'UZS')}</b>\n")
    lines.append("<b>Fondlar:</b>")
    for f in funds:
        lines.append(f"• {f['name']}: {fmt_money(f['balance_uzs'], 'UZS')}")
    return "\n".join(lines)


async def _debt_text() -> str:
    async with acquire() as conn:
        rows = await conn.fetch(
            """SELECT direction, counterparty_name, currency, remaining, due_date, status
               FROM v_debt_outstanding WHERE remaining > 0
               ORDER BY due_date NULLS LAST"""
        )
    if not rows:
        return "💳 <b>Qarz hisoboti</b>\n\nFaol qarzlar yo'q. ✅"
    lent = [r for r in rows if r["direction"] == "lent"]
    borrowed = [r for r in rows if r["direction"] == "borrowed"]
    lines = ["💳 <b>Qarz hisoboti</b>\n"]
    lines.append("📥 <b>Menga qarzdor:</b>")
    lines.extend(
        f"• {r['counterparty_name']}: {fmt_money(r['remaining'], r['currency'])} "
        f"(muddat: {fmt_date(r['due_date'])})" for r in lent
    ) if lent else lines.append("  —")
    lines.append("\n📤 <b>Men qaytarishim kerak:</b>")
    lines.extend(
        f"• {r['counterparty_name']}: {fmt_money(r['remaining'], r['currency'])} "
        f"(muddat: {fmt_date(r['due_date'])})" for r in borrowed
    ) if borrowed else lines.append("  —")
    return "\n".join(lines)


async def _transfers_text() -> str:
    async with acquire() as conn:
        rows = await conn.fetch(
            """SELECT t.transfer_group_id AS gid,
                      MIN(t.occurred_at) AS at,
                      MAX(t.amount_uzs) FILTER (WHERE t.kind = 'transfer_out') AS amount_uzs,
                      MAX(w.name) FILTER (WHERE t.kind = 'transfer_out') AS src,
                      MAX(w.name) FILTER (WHERE t.kind = 'transfer_in') AS dst
               FROM transactions t JOIN wallets w ON w.id = t.wallet_id
               WHERE t.kind IN ('transfer_out', 'transfer_in') AND t.transfer_group_id IS NOT NULL
               GROUP BY t.transfer_group_id
               ORDER BY at DESC LIMIT 10"""
        )
    if not rows:
        return "🔄 <b>Transfer tarixi</b>\n\nTransferlar yo'q."
    lines = ["🔄 <b>Transfer tarixi</b> (so'nggi 10)\n"]
    for r in rows:
        when = r["at"].strftime("%d.%m.%Y") if r["at"] else ""
        lines.append(f"• {when}: {r['src']} → {r['dst']} — {fmt_money(r['amount_uzs'], 'UZS')}")
    return "\n".join(lines)
