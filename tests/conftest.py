import os

os.environ.setdefault("BOT_TOKEN", "123:test")
os.environ.setdefault(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/imed_finance_test"
)

import pytest
import pytest_asyncio

from app.db import init_pool, close_pool, pool as get_pool


@pytest_asyncio.fixture(autouse=True)
async def clean_db():
    """Har bir test o'ziga xos event loopda ishlaydi (pytest-asyncio
    function-scope), shuning uchun DB pool ham har bir test uchun alohida
    ochilib yopiladi — aks holda boshqa loopga bog'langan pool xato beradi.
    Statik spravochnik (wallets/funds/...) qoladi, faqat testlar orasida
    to'planadigan yozuvlar tozalanadi."""
    await init_pool()
    async with get_pool().acquire() as conn:
        await conn.execute(
            "TRUNCATE transactions, debt_payments, debts, exchange_rates, "
            "audit_logs, users RESTART IDENTITY CASCADE"
        )
    yield
    await close_pool()
