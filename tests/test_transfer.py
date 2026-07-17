from aiogram.fsm.storage.memory import MemoryStorage

from app.db import pool
from app.handlers import transfer
from tests.helpers import FakeCallback, FakeMessage, fsm_state, make_user, wallet_balance, wallet_id


async def test_transfer_moves_balance_atomically_between_uzs_wallets():
    await make_user("admin", 3001)
    naqd = await wallet_id("Naqd UZS")
    karta = await wallet_id("Karta UZS")

    async with pool().acquire() as conn:
        await conn.execute(
            """INSERT INTO transactions (kind, wallet_id, amount, currency, fx_rate, amount_uzs, created_by)
               VALUES ('opening', $1, 1000000, 'UZS', 1, 1000000, (SELECT id FROM users WHERE telegram_id=3001))""",
            naqd,
        )

    state = fsm_state(MemoryStorage(), 3001)
    await transfer.cmd_transfer(FakeMessage(3001), state)
    await transfer.cb_source_chosen(FakeCallback(f"trsrc:{naqd}", 3001), state)
    await transfer.cb_dest_chosen(FakeCallback(f"trdst:{karta}", 3001), state)
    await transfer.msg_amount_entered(FakeMessage(3001, text="300000"), state)
    await transfer.msg_description_entered(FakeMessage(3001, text="-"), state)

    assert await wallet_balance(naqd) == 700000
    assert await wallet_balance(karta) == 300000


async def test_transfer_rejects_insufficient_balance():
    await make_user("admin", 3002)
    naqd = await wallet_id("Naqd UZS")
    karta = await wallet_id("Karta UZS")

    state = fsm_state(MemoryStorage(), 3002)
    await transfer.cmd_transfer(FakeMessage(3002), state)
    await transfer.cb_source_chosen(FakeCallback(f"trsrc:{naqd}", 3002), state)
    await transfer.cb_dest_chosen(FakeCallback(f"trdst:{karta}", 3002), state)

    m = FakeMessage(3002, text="999999999")
    await transfer.msg_amount_entered(m, state)
    assert any("yetarli mablag'" in a for a in m.answers)
    assert await state.get_state() == transfer.TransferFlow.entering_amount.state


async def test_transfer_source_only_offers_same_currency_destinations():
    await make_user("admin", 3003)
    naqd = await wallet_id("Naqd UZS")

    state = fsm_state(MemoryStorage(), 3003)
    await transfer.cmd_transfer(FakeMessage(3003), state)
    cb = FakeCallback(f"trsrc:{naqd}", 3003)
    await transfer.cb_source_chosen(cb, state)

    assert await state.get_state() == transfer.TransferFlow.choosing_dest.state
    # USD kassa (boshqa valyuta) maqsad sifatida taklif qilinmasligi kerak
    dest_markup = cb.message.markups[-1]
    button_texts = [btn.text for row in dest_markup.inline_keyboard for btn in row]
    assert not any("USD" in t for t in button_texts)
    assert any("Karta UZS" in t for t in button_texts)
