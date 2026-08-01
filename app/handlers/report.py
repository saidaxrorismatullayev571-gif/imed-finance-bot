"""Excel/PDF hisobot — Faza 3.

`/hisobot` — davr tanlanadi (bugun/hafta/oy/hammasi), keyin format
tanlanadi (Excel yoki PDF), tranzaksiyalar va joriy balanslar bitta
faylga yig'ilib, Telegram orqali hujjat sifatida yuboriladi.

Web App dashboard — alohida infratuzilma (HTTP server, HTTPS, Telegram
WebApp) talab qiladi, shuning uchun bu faylda emas."""

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
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

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
FORMAT_LABEL = {"xlsx": "📊 Excel (.xlsx)", "pdf": "📄 PDF"}


def _money(value) -> str:
    return f"{float(value):,.0f}".replace(",", " ")


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


_TABLE_HEADER_STYLE = [
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTSIZE", (0, 0), (-1, -1), 8),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
]


def _build_pdf(rows, wallets, funds, period_label: str) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4), topMargin=15 * mm, bottomMargin=15 * mm,
        leftMargin=12 * mm, rightMargin=12 * mm,
    )
    styles = getSampleStyleSheet()
    elements = [Paragraph(f"iMed Moliya hisoboti — {period_label}", styles["Title"]), Spacer(1, 8)]

    txn_data = [["Sana", "Turi", "Kassa", "Summa", "Valyuta", "Summa (UZS)", "Kategoriya/Manba", "Izoh", "Kim"]]
    for r in rows:
        txn_data.append(
            [
                r["occurred_at"].strftime("%Y-%m-%d %H:%M"),
                KIND_LABEL.get(r["kind"], r["kind"]),
                r["wallet_name"],
                _money(r["amount"]),
                r["currency"],
                _money(r["amount_uzs"]),
                r["category_or_source"] or "",
                (r["description"] or "")[:40],
                r["created_by"],
            ]
        )
    txn_table = Table(txn_data, repeatRows=1)
    txn_table.setStyle(TableStyle(
        _TABLE_HEADER_STYLE
        + [("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")])]
    ))
    elements.append(txn_table)
    elements.append(Spacer(1, 14))

    elements.append(Paragraph("Kassa balanslari", styles["Heading2"]))
    bal_data = [["Kassa", "Valyuta", "Balans (UZS)"]]
    for w in wallets:
        bal_data.append([w["name"], w["currency"], _money(w["balance_uzs"])])
    bal_table = Table(bal_data)
    bal_table.setStyle(TableStyle(_TABLE_HEADER_STYLE))
    elements.append(bal_table)

    if funds:
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("Fond balanslari", styles["Heading2"]))
        fund_data = [["Fond", "Balans (UZS)"]]
        for f in funds:
            fund_data.append([f["name"], _money(f["balance_uzs"])])
        fund_table = Table(fund_data)
        fund_table.setStyle(TableStyle(_TABLE_HEADER_STYLE))
        elements.append(fund_table)

    doc.build(elements)
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

    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"repfmt:{fmt}:{period}")]
        for fmt, label in FORMAT_LABEL.items()
    ]
    await callback.message.edit_text(
        f"{PERIOD_LABEL[period]} — qaysi formatda?", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("repfmt:"))
async def cb_report_format(callback: CallbackQuery) -> None:
    _, fmt, period = callback.data.split(":", 2)
    if period not in PERIOD_SQL or fmt not in FORMAT_LABEL:
        await callback.answer("Noto'g'ri so'rov.", show_alert=True)
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

    if fmt == "xlsx":
        content = _build_workbook(rows, wallets, funds)
        filename = f"hisobot_{period}.xlsx"
    else:
        content = _build_pdf(rows, wallets, funds, PERIOD_LABEL[period])
        filename = f"hisobot_{period}.pdf"

    doc = BufferedInputFile(content, filename=filename)
    await callback.message.answer_document(
        doc, caption=f"📊 Hisobot — {PERIOD_LABEL[period]} ({len(rows)} ta tranzaksiya)"
    )
    await callback.answer()
