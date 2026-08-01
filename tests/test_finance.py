from decimal import Decimal

from aiogram.fsm.storage.memory import MemoryStorage

from app.db import pool
from app.handlers import finance
from tests.helpers import (
    FakeCallback,
    FakeMessage,
    expense_category_id,
    fsm_state,
    income_source_id,
    make_user,
    wallet_balance,
    wallet_id,
)


async def test_viewer_cannot_record_income():
    await make_user("viewer", 1001)
    state = fsm_state(MemoryStorage(), 1001)
    m = FakeMessage(1001)
    await finance.cmd_income(m, state)
    assert any("huquqi yo'q" in a for a in m.answers)
    assert await state.get_state() is None


async def test_full_income_flow_records_transaction_and_updates_balance():
    admin_id = await make_user("admin", 1002)
    wid = await wallet_id()
    sid = await income_source_id()
    state = fsm_state(MemoryStorage(), 1002)

    await finance.cmd_income(FakeMessage(1002), state)
    assert await state.get_state() == finance.RecordTxn.choosing_wallet.state

    await finance.cb_wallet_chosen(FakeCallback(f"txw:{wid}", 1002), state)
    assert await state.get_state() == finance.RecordTxn.choosing_category.state

    await finance.cb_category_chosen(FakeCallback(f"txc:{sid}", 1002), state)
    assert await state.get_state() == finance.RecordTxn.entering_amount.state

    before = await wallet_balance(wid)
    await finance.msg_amount_entered(FakeMessage(1002, text="150 000"), state)
    assert await state.get_state() == finance.RecordTxn.entering_description.state

    await finance.msg_description_entered(FakeMessage(1002, text="-"), state)
    assert await state.get_state() is None

    after = await wallet_balance(wid)
    assert after - before == 150000

    async with pool().acquire() as conn:
        txn = await conn.fetchrow(
            "SELECT kind, amount_uzs, source_id, created_by FROM transactions "
            "WHERE wallet_id = $1 ORDER BY id DESC LIMIT 1",
            wid,
        )
    assert txn["kind"] == "income"
    assert txn["amount_uzs"] == Decimal("150000.00")
    assert txn["source_id"] == sid
    assert txn["created_by"] == admin_id


async def test_expense_flow_decreases_balance():
    await make_user("manager", 1003)
    wid = await wallet_id()
    cid = await expense_category_id()
    state = fsm_state(MemoryStorage(), 1003)

    await finance.cmd_expense(FakeMessage(1003), state)
    await finance.cb_wallet_chosen(FakeCallback(f"txw:{wid}", 1003), state)
    await finance.cb_category_chosen(FakeCallback(f"txc:{cid}", 1003), state)

    before = await wallet_balance(wid)
    await finance.msg_amount_entered(FakeMessage(1003, text="50000"), state)
    await finance.msg_description_entered(FakeMessage(1003, text="Oylik ijara"), state)
    after = await wallet_balance(wid)

    assert before - after == 50000


async def test_invalid_amount_is_rejected_and_state_unchanged():
    await make_user("admin", 1004)
    wid = await wallet_id()
    sid = await income_source_id()
    state = fsm_state(MemoryStorage(), 1004)

    await finance.cmd_income(FakeMessage(1004), state)
    await finance.cb_wallet_chosen(FakeCallback(f"txw:{wid}", 1004), state)
    await finance.cb_category_chosen(FakeCallback(f"txc:{sid}", 1004), state)

    bad = FakeMessage(1004, text="abc")
    await finance.msg_amount_entered(bad, state)
    assert await state.get_state() == finance.RecordTxn.entering_amount.state
    assert any("Noto'g'ri summa" in a for a in bad.answers)


async def test_usd_wallet_without_fx_rate_is_refused():
    await make_user("admin", 1005)
    usd_wallet = await wallet_id("Naqd USD")
    state = fsm_state(MemoryStorage(), 1005)

    await finance.cmd_expense(FakeMessage(1005), state)
    cb = FakeCallback(f"txw:{usd_wallet}", 1005)
    await finance.cb_wallet_chosen(cb, state)

    assert await state.get_state() is None
    assert any("kursi hali kiritilmagan" in e for e in cb.message.edits)


async def test_balance_command_lists_wallets():
    await make_user("viewer", 1006)
    m = FakeMessage(1006)
    await finance.cmd_balance(m)
    assert any("Naqd UZS" in a for a in m.answers)
