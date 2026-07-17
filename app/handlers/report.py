"""Excel hisobot — Faza 3 boshlanishi.

`/hisobot` — davr tanlanadi (bugun/hafta/oy/hammasi), tranzaksiyalar va
joriy balanslar bitta .xlsx faylga yig'ilib, Telegram orqali hujjat
sifatida yuboriladi. PDF va Web App dashboard — keyingi bosqich."""

import io

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from openpyxl import Workbook

from app.db import acquire
from app.handlers.finance import _get_user

router = Router()

PERIOD_LABEL = {"today": "Bugun", "week": "Shu hafta", "month": "Shu oy", "all": "Hammasi"}
PERIOD_SQL = {
    "today": "t.occurred_at >= date_trunc('day', now())",
    "week": "t.occurred_at >= date_trunc('week', now())",
    "month": "t.occurred_at >= date_trunc('month', now())",
    "all": "TRUE",
}
KIND_LABEL = {
    "opening": "Boshlang'ich balans",
    "income": "Kirim",
    "expense": "Chiqim",
    "transfer_out": "Transfer (chiqish)",
    "transfer_in": "Transfer (kirish)",
    "debt_out": "Qarz berish",
    "debt_in": "Qarz olish",
    "debt_repay_out": "Qarz qaytarish",
}


def _build_workbook(rows, wallets, funds) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Tranzaksiyalar"
    ws.append(
        ["Sana", "Turi", "Kassa", "Summa", "Valyuta", "Summa (UZS)", "Kategoriya/Manba", "Izoh", "Kim yozgan"]
    )
    for r in rows:
        ws.append(
            [
                r["occurred_at"].strftime("%Y-%m-%d %H:%M"),
                KIND_LABEL.get(r["kind"], r["kind"]),
                r["wallet_name"],
                float(r["amount"]),
                r["currency"],
                float(r["amount_uzs"]),
                r["category_or_source"] or "",
                r["description"] or "",
                r["created_by"],
            ]
        )

    ws2 = wb.create_sheet("Balanslar")
    ws2.append(["Kassa", "Valyuta", "Balans (UZS)"])
    for w in wallets:
        ws2.append([w["name"], w["currency"], float(w["balance_uzs"])])
    ws2.append([])
    ws2.append(["Fond", "", "Balans (UZS)"])
    for f in funds:
        ws2.append([f["name"], "", float(f["balance_uzs"])])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@router.message(Command("hisobot"))
async def cmd_report(message: Message) -> None:
    async with acquire() as conn:
        user = await _get_user(conn, message.from_user.id)
    if user is None:
        await message.answer("Avval ro'yxatdan o'ting: /start")
        return

    rows = [[InlineKeyboardButton(text=label, callback_data=f"rep:{key}")] for key, label in PERIOD_LABEL.items()]
    await message.answer(
        "Hisobot uchun davrni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )


@router.callback_query(F.data.startswith("rep:"))
async def cb_report_period(callback: CallbackQuery) -> None:
    period = callback.data.split(":", 1)[1]
    if period not in PERIOD_SQL:
        await callback.answer("Noto'g'ri davr.", show_alert=True)
        return

    async with acquire() as conn:
        user = await _get_user(conn, callback.from_user.id)
        if user is None:
            await callback.answer("Avval ro'yxatdan o'ting.", show_alert=True)
            return
        rows = await conn.fetch(
            f"""
            SELECT t.occurred_at, t.kind, w.name AS wallet_name, t.amount, t.currency, t.amount_uzs,
                   COALESCE(s.name, c.name) AS category_or_source, t.description, u.full_name AS created_by
            FROM transactions t
            JOIN wallets w ON w.id = t.wallet_id
            LEFT JOIN income_sources s ON s.id = t.source_id
            LEFT JOIN expense_categories c ON c.id = t.category_id
            JOIN users u ON u.id = t.created_by
            WHERE {PERIOD_SQL[period]}
            ORDER BY t.occurred_at
            """
        )
        wallets = await conn.fetch("SELECT name, currency, balance_uzs FROM v_wallet_balances ORDER BY name")
        funds = await conn.fetch("SELECT name, balance_uzs FROM v_fund_balances ORDER BY name")

    content = _build_workbook(rows, wallets, funds)
    doc = BufferedInputFile(content, filename=f"hisobot_{period}.xlsx")
    await callback.message.answer_document(
        doc, caption=f"📊 Hisobot — {PERIOD_LABEL[period]} ({len(rows)} ta tranzaksiya)"
    )
    await callback.answer()
