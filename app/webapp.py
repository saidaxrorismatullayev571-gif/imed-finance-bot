"""Web App dashboard — Telegram WebApp orqali ochiladigan, faqat o'qish
uchun balans/tranzaksiya ko'rinishi.

Xavfsizlik: har bir /api/dashboard so'rovi Telegram'ning initData imzosi
bilan tasdiqlanadi (webapp_auth.validate_init_data) — shuning uchun URL
o'zi ochiq bo'lsa ham, faqat haqiqiy Telegram mijozidan, ro'yxatdan
o'tgan foydalanuvchi nomidan kelgan so'rovlargina ma'lumot oladi.

Bu server aiogram polling bilan BIR XIL processda, bot.py'dan ishga
tushiriladi (WEBAPP_URL sozlangan bo'lsa)."""

import json

from aiohttp import web

from app.config import config
from app.db import pool
from app.webapp_auth import validate_init_data

DASHBOARD_HTML = """<!doctype html>
<html lang="uz">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>iMed Moliya — Dashboard</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
  :root { color-scheme: light dark; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    margin: 0; padding: 16px;
    background: var(--tg-theme-bg-color, #ffffff);
    color: var(--tg-theme-text-color, #111111);
  }
  h1 { font-size: 18px; margin: 0 0 12px; }
  h2 { font-size: 14px; opacity: .7; margin: 20px 0 8px; text-transform: uppercase; letter-spacing: .04em; }
  .card {
    background: var(--tg-theme-secondary-bg-color, #f4f4f5);
    border-radius: 12px; padding: 12px 14px; margin-bottom: 8px;
    display: flex; justify-content: space-between; align-items: center;
  }
  .card .name { font-weight: 600; }
  .card .sub { font-size: 12px; opacity: .6; }
  .card .amount { font-variant-numeric: tabular-nums; font-weight: 600; }
  .amount.neg { color: #dc2626; }
  .txn { font-size: 13px; }
  .txn .row1 { display: flex; justify-content: space-between; }
  .txn .row2 { font-size: 11px; opacity: .6; }
  .muted { opacity: .6; font-size: 13px; text-align: center; padding: 20px 0; }
  .error { color: #dc2626; text-align: center; padding: 20px 0; }
</style>
</head>
<body>
<h1>💰 iMed Moliya — Dashboard</h1>
<div id="root"><p class="muted">Yuklanmoqda...</p></div>
<script>
const tg = window.Telegram && window.Telegram.WebApp;
if (tg) { tg.ready(); tg.expand(); }

function money(n) {
  return Math.round(n).toLocaleString('fr-FR').replace(/,/g, ' ') + " UZS";
}

async function load() {
  const root = document.getElementById('root');
  if (!tg || !tg.initData) {
    root.innerHTML = '<p class="error">Bu sahifa faqat Telegram ilovasi ichida ochilishi kerak.</p>';
    return;
  }
  try {
    const res = await fetch('/api/dashboard', { headers: { 'X-Telegram-Init-Data': tg.initData } });
    if (!res.ok) {
      root.innerHTML = '<p class="error">Ruxsat yo\\'q yoki ro\\'yxatdan o\\'tmagansiz. Botga /start yuboring.</p>';
      return;
    }
    const data = await res.json();
    let html = '<h2>Kassalar</h2>';
    for (const w of data.wallets) {
      const cls = w.balance_uzs < 0 ? 'amount neg' : 'amount';
      html += `<div class="card"><div><div class="name">${w.name}</div><div class="sub">${w.currency}</div></div><div class="${cls}">${money(w.balance_uzs)}</div></div>`;
    }
    html += '<h2>Fondlar</h2>';
    for (const f of data.funds) {
      const cls = f.balance_uzs < 0 ? 'amount neg' : 'amount';
      html += `<div class="card"><div class="name">${f.name}</div><div class="${cls}">${money(f.balance_uzs)}</div></div>`;
    }
    html += '<h2>So\\'nggi tranzaksiyalar</h2>';
    if (data.transactions.length === 0) {
      html += '<p class="muted">Hali tranzaksiya yo\\'q.</p>';
    }
    for (const t of data.transactions) {
      const sign = ['income', 'opening', 'transfer_in', 'debt_in'].includes(t.kind) ? '+' : '-';
      const cls = sign === '+' ? 'amount' : 'amount neg';
      html += `<div class="card txn"><div style="flex:1"><div class="row1"><span>${t.kind_label}</span><span class="${cls}">${sign}${money(t.amount_uzs)}</span></div><div class="row2">${t.wallet_name} · ${t.occurred_at}</div></div></div>`;
    }
    root.innerHTML = html;
  } catch (e) {
    root.innerHTML = '<p class="error">Xatolik yuz berdi.</p>';
  }
}
load();
</script>
</body>
</html>"""

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


async def handle_index(request: web.Request) -> web.Response:
    return web.Response(text=DASHBOARD_HTML, content_type="text/html")


async def handle_dashboard_api(request: web.Request) -> web.Response:
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    parsed = validate_init_data(init_data, config.bot_token)
    if parsed is None or "user" not in parsed:
        return web.json_response({"error": "invalid initData"}, status=401)

    telegram_id = parsed["user"].get("id")
    async with pool().acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id FROM users WHERE telegram_id = $1 AND is_active", telegram_id
        )
        if user is None:
            return web.json_response({"error": "not registered"}, status=403)

        wallets = await conn.fetch(
            "SELECT name, currency, balance_uzs FROM v_wallet_balances ORDER BY name"
        )
        funds = await conn.fetch("SELECT name, balance_uzs FROM v_fund_balances ORDER BY name")
        transactions = await conn.fetch(
            """SELECT t.kind, w.name AS wallet_name, t.amount_uzs, t.occurred_at
               FROM transactions t
               JOIN wallets w ON w.id = t.wallet_id
               ORDER BY t.occurred_at DESC
               LIMIT 15"""
        )

    return web.json_response(
        {
            "wallets": [
                {"name": w["name"], "currency": w["currency"], "balance_uzs": float(w["balance_uzs"])}
                for w in wallets
            ],
            "funds": [{"name": f["name"], "balance_uzs": float(f["balance_uzs"])} for f in funds],
            "transactions": [
                {
                    "kind": t["kind"],
                    "kind_label": KIND_LABEL.get(t["kind"], t["kind"]),
                    "wallet_name": t["wallet_name"],
                    "amount_uzs": float(t["amount_uzs"]),
                    "occurred_at": t["occurred_at"].strftime("%Y-%m-%d %H:%M"),
                }
                for t in transactions
            ],
        }
    )


def build_webapp() -> web.Application:
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/dashboard", handle_dashboard_api)
    return app
