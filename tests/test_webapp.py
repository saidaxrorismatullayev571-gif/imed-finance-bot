import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from aiohttp.test_utils import TestClient, TestServer

from app.db import pool
from app.webapp import build_webapp
from tests.helpers import make_user, wallet_id

BOT_TOKEN = "123:test"  # tests/conftest.py da os.environ.setdefault bilan mos


def _init_data(telegram_id: int, token: str = BOT_TOKEN) -> str:
    fields = {
        "query_id": "AA1",
        "user": json.dumps({"id": telegram_id, "first_name": "T"}, separators=(",", ":")),
        "auth_date": str(int(time.time())),
    }
    dcs = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    h = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": h})


async def test_index_serves_html():
    async with TestClient(TestServer(build_webapp())) as client:
        resp = await client.get("/")
        assert resp.status == 200
        text = await resp.text()
        assert "Dashboard" in text
        assert "telegram-web-app.js" in text


async def test_dashboard_api_requires_init_data_header():
    async with TestClient(TestServer(build_webapp())) as client:
        resp = await client.get("/api/dashboard")
        assert resp.status == 401


async def test_dashboard_api_rejects_tampered_init_data():
    async with TestClient(TestServer(build_webapp())) as client:
        bad = _init_data(6001).replace("6001", "9999")
        resp = await client.get("/api/dashboard", headers={"X-Telegram-Init-Data": bad})
        assert resp.status == 401


async def test_dashboard_api_rejects_unregistered_user():
    async with TestClient(TestServer(build_webapp())) as client:
        resp = await client.get(
            "/api/dashboard", headers={"X-Telegram-Init-Data": _init_data(424242)}
        )
        assert resp.status == 403


async def test_dashboard_api_returns_real_balances_and_transactions():
    await make_user("viewer", 6001)
    wid = await wallet_id()
    async with pool().acquire() as conn:
        admin_id = await conn.fetchval("SELECT id FROM users WHERE telegram_id = 6001")
        await conn.execute(
            """INSERT INTO transactions (kind, wallet_id, amount, currency, fx_rate, amount_uzs, created_by)
               VALUES ('opening', $1, 250000, 'UZS', 1, 250000, $2)""",
            wid, admin_id,
        )

    async with TestClient(TestServer(build_webapp())) as client:
        resp = await client.get(
            "/api/dashboard", headers={"X-Telegram-Init-Data": _init_data(6001)}
        )
        assert resp.status == 200
        data = await resp.json()

    naqd = next(w for w in data["wallets"] if w["name"] == "Naqd UZS")
    assert naqd["balance_uzs"] == 250000.0
    assert len(data["transactions"]) == 1
    assert data["transactions"][0]["kind_label"] == "Boshlang'ich balans"
    assert data["transactions"][0]["wallet_name"] == "Naqd UZS"
