from decimal import Decimal

from aiogram.fsm.storage.memory import MemoryStorage

from app.db import pool
from app.handlers import finance, setup
from tests.helpers import FakeCallback, FakeMessage, fsm_state, make_user, wallet_balance, wallet_id


async def test_rate_command_requires_admin():
    await make_user("manager", 2001)
    m = FakeMessage(2001)
    await setup.cmd_rate(m, fsm_state(MemoryStorage(), 2001))
    assert any("administrator" in a for a in m.answers)


async def test_rate_is_stored():
    await make_user("admin", 2002)
    state = fsm_state(MemoryStorage(), 2002)
    await setup.cmd_rate(FakeMessage(2002), state)
    await setup.cb_rate_currency(FakeCallback("fxc:USD", 2002), state)
    await setup.msg_rate_value(FakeMessage(2002, text="12 650"), state)

    async with pool().acquire() as conn:
        rate = await conn.fetchval(
            "SELECT rate_uzs FROM exchange_rates WHERE currency = 'USD' "
            "ORDER BY fetched_at DESC LIMIT 1"
        )
    assert rate == Decimal("12650")


async def test_invalid_rate_is_rejected():
    await make_user("admin", 2003)
    state = fsm_state(MemoryStorage(), 2003)
    await setup.cmd_rate(FakeMessage(2003), state)
    await setup.cb_rate_currency(FakeCallback("fxc:USD", 2003), state)
    bad = FakeMessage(2003, text="abc")
    await setup.msg_rate_value(bad, state)
    assert await state.get_state() == setup.SetRate.entering_rate.state
    assert any("Noto'g'ri kurs" in a for a in bad.answers)


async def test_opening_balance_usd_after_rate_set_and_unlocks_usd_wallet():
    await make_user("admin", 2004)
    usd_wallet = await wallet_id("Naqd USD")

    rate_state = fsm_state(MemoryStorage(), 2004)
    await setup.cmd_rate(FakeMessage(2004), rate_state)
    await setup.cb_rate_currency(FakeCallback("fxc:USD", 2004), rate_state)
    await setup.msg_rate_value(FakeMessage(2004, text="12650"), rate_state)

    open_state = fsm_state(MemoryStorage(), 2004)
    await setup.cmd_opening(FakeMessage(2004), open_state)
    await setup.cb_opening_wallet(FakeCallback(f"opw:{usd_wallet}", 2004), open_state)
    await setup.msg_opening_amount(FakeMessage(2004, text="100"), open_state)

    balance = await wallet_balance(usd_wallet)
    assert balance == Decimal("1265000.00")

    async with pool().acquire() as conn:
        txn = await conn.fetchrow(
            "SELECT kind, fx_rate FROM transactions WHERE wallet_id = $1 ORDER BY id DESC LIMIT 1",
            usd_wallet,
        )
    assert txn["kind"] == "opening"
    assert txn["fx_rate"] == Decimal("12650.000000")

    # Endi USD kassaga /chiqim ham ishlashi kerak (kurs allaqachon bor)
    expense_state = fsm_state(MemoryStorage(), 2004)
    await finance.cmd_expense(FakeMessage(2004), expense_state)
    cb = FakeCallback(f"txw:{usd_wallet}", 2004)
    await finance.cb_wallet_chosen(cb, expense_state)
    assert await expense_state.get_state() == finance.RecordTxn.choosing_category.state


async def test_opening_balance_uzs_no_rate_needed():
    await make_user("admin", 2005)
    wid = await wallet_id("Naqd UZS")
    state = fsm_state(MemoryStorage(), 2005)

    await setup.cmd_opening(FakeMessage(2005), state)
    await setup.cb_opening_wallet(FakeCallback(f"opw:{wid}", 2005), state)
    await setup.msg_opening_amount(FakeMessage(2005, text="500000"), state)

    assert await wallet_balance(wid) == Decimal("500000.00")
