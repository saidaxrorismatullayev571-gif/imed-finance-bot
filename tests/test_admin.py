from aiogram.fsm.storage.memory import MemoryStorage

from app.db import pool
from app.handlers import admin
from tests.helpers import FakeCallback, FakeMessage, fsm_state, make_user


async def test_users_list_requires_admin():
    await make_user("manager", 5001)
    m = FakeMessage(5001)
    await admin.cmd_users(m)
    assert any("administrator" in a for a in m.answers)


async def test_users_list_shows_everyone():
    await make_user("admin", 5002)
    await make_user("viewer", 5003)
    m = FakeMessage(5002)
    await admin.cmd_users(m)
    text = m.answers[0]
    assert "Administrator" in text
    assert "Kuzatuvchi" in text


async def test_change_role_excludes_self_from_target_list():
    await make_user("admin", 5010)
    m = FakeMessage(5010)
    await admin.cmd_change_role(m, fsm_state(MemoryStorage(), 5010))
    assert any("boshqa foydalanuvchi yo'q" in a for a in m.answers)


async def test_change_role_full_flow_updates_role():
    await make_user("admin", 5011)
    target_id = await make_user("viewer", 5012, phone="+998900000012")

    state = fsm_state(MemoryStorage(), 5011)
    await admin.cmd_change_role(FakeMessage(5011), state)
    assert await state.get_state() == admin.ChangeRole.choosing_user.state

    cb = FakeCallback(f"roleu:{target_id}", 5011)
    await admin.cb_user_chosen(cb, state)
    assert await state.get_state() == admin.ChangeRole.choosing_role.state

    cb2 = FakeCallback("roler:manager", 5011)
    await admin.cb_role_chosen(cb2, state)

    async with pool().acquire() as conn:
        role = await conn.fetchval("SELECT role FROM users WHERE id = $1", target_id)
    assert role == "manager"
    assert await state.get_state() is None


async def test_cannot_demote_sole_remaining_admin():
    """Himoya to'g'ridan-to'g'ri callback darajasida tekshiriladi: agar
    tizimda faqat bitta admin qolgan bo'lsa, uni pastga tushirish rad
    etilishi kerak (odatiy /rol oqimida o'zingizni tanlab bo'lmaydi, lekin
    bu himoya kelajakda shart o'zgarsa ham ishlashi kerak)."""
    admin_id = await make_user("admin", 5013)

    state = fsm_state(MemoryStorage(), 5013)
    await state.update_data(target_id=admin_id, target_name="Sole Admin")
    await state.set_state(admin.ChangeRole.choosing_role)

    cb = FakeCallback("roler:viewer", 5013)
    await admin.cb_role_chosen(cb, state)

    async with pool().acquire() as conn:
        role = await conn.fetchval("SELECT role FROM users WHERE id = $1", admin_id)
    assert role == "admin"
    assert any("yagona administratori" in e for e in cb.message.edits)


async def test_can_demote_admin_when_another_admin_remains():
    await make_user("admin", 5015)
    target_id = await make_user("admin", 5016, phone="+998900000016")

    state = fsm_state(MemoryStorage(), 5015)
    await state.update_data(target_id=target_id, target_name="Second Admin")
    await state.set_state(admin.ChangeRole.choosing_role)

    cb = FakeCallback("roler:viewer", 5015)
    await admin.cb_role_chosen(cb, state)

    async with pool().acquire() as conn:
        role = await conn.fetchval("SELECT role FROM users WHERE id = $1", target_id)
    assert role == "viewer"


async def test_audit_requires_admin():
    await make_user("viewer", 5020)
    m = FakeMessage(5020)
    await admin.cmd_audit(m)
    assert any("administrator" in a for a in m.answers)


async def test_audit_shows_recent_entries():
    admin_id = await make_user("admin", 5021)
    async with pool().acquire() as conn:
        wid = await conn.fetchval("SELECT id FROM wallets WHERE name = 'Naqd UZS'")
        await conn.execute("SELECT set_config('app.actor_id', $1, true)", str(admin_id))
        await conn.execute(
            """INSERT INTO transactions (kind, wallet_id, amount, currency, fx_rate, amount_uzs, created_by)
               VALUES ('opening', $1, 100000, 'UZS', 1, 100000, $2)""",
            wid, admin_id,
        )
    m = FakeMessage(5021)
    await admin.cmd_audit(m)
    text = m.answers[0]
    assert "transactions" in text
    assert "qo'shildi" in text
