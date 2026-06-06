"""Telegram Web App dashboard — FastAPI (JSON API + statik fayllar).

Botdan alohida jarayon sifatida ishlaydi (docker-compose `webapp` xizmati).
DATABASE_URL bot bilan bir xil bazaga ulanadi, faqat o'qiydi (balans view'lari).
"""
import os
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

DATABASE_URL = os.environ.get("DATABASE_URL", "")

_pool: asyncpg.Pool | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool
    _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    yield
    if _pool is not None:
        await _pool.close()


app = FastAPI(title="iMed Finance Dashboard", lifespan=lifespan)


@app.get("/api/summary")
async def summary() -> dict:
    """Dashboard uchun yig'ma ma'lumot (barcha grafiklar shu yerdan)."""
    async with _pool.acquire() as conn:
        wallets = await conn.fetch(
            "SELECT name, balance_uzs FROM v_wallet_balances ORDER BY name"
        )
        funds = await conn.fetch("SELECT name, balance_uzs FROM v_fund_balances ORDER BY name")
        pnl = await conn.fetch(
            """SELECT to_char(date_trunc('month', occurred_at), 'YYYY-MM') AS month,
                      COALESCE(SUM(amount_uzs) FILTER (WHERE kind = 'income'), 0) AS income,
                      COALESCE(SUM(amount_uzs) FILTER (WHERE kind = 'expense'), 0) AS expense
               FROM transactions WHERE kind IN ('income', 'expense')
               GROUP BY 1 ORDER BY 1 ASC"""
        )
        categories = await conn.fetch(
            """SELECT c.name, COALESCE(SUM(t.amount_uzs), 0) AS total
               FROM transactions t JOIN expense_categories c ON c.id = t.category_id
               WHERE t.kind = 'expense' GROUP BY c.name ORDER BY total DESC"""
        )
        debts = await conn.fetch(
            """SELECT direction, COALESCE(SUM(remaining), 0) AS total
               FROM v_debt_outstanding WHERE remaining > 0 GROUP BY direction"""
        )

    def f(v) -> float:
        return float(v)

    debt_map = {d["direction"]: f(d["total"]) for d in debts}
    return {
        "wallets": [{"name": w["name"], "balance": f(w["balance_uzs"])} for w in wallets],
        "funds": [{"name": x["name"], "balance": f(x["balance_uzs"])} for x in funds],
        "pnl": [
            {"month": r["month"], "income": f(r["income"]), "expense": f(r["expense"])}
            for r in pnl
        ],
        "categories": [{"name": c["name"], "total": f(c["total"])} for c in categories],
        "debts": {"lent": debt_map.get("lent", 0.0), "borrowed": debt_map.get("borrowed", 0.0)},
    }


# Statik fayllar (index.html) — eng oxirida mount qilinadi, API yo'llardan keyin
app.mount("/", StaticFiles(directory="webapp/static", html=True), name="static")
