from aiogram.fsm.storage.memory import MemoryStorage

from app.db import pool
from app.handlers import start
from tests.helpers import FakeBot, FakeContact, FakeMessage, make_user


async def test_contact_spoofing_is_rejected():
    """Boshqa birovning kontakt-kartasi yuborilsa (contact.user_id !=
    from_user.id), ro'yxatdan o'tish rad etilishi kerak."""
    bot = FakeBot()
    other_persons_contact = FakeContact(user_id=999999)
    m = FakeMessage(1001, contact=other_persons_contact)
    await start.got_contact(m, bot)

    async with pool().acquire() as conn:
        exists = await conn.fetchval("SELECT 1 FROM users WHERE telegram_id = $1", 1001)
    assert exists is None
    assert any("o'zingizning raqamingizni" in a for a in m.answers)


async def test_own_contact_registers_and_sets_command_menu():
    bot = FakeBot()
    own_contact = FakeContact(user_id=1002)
    m = FakeMessage(1002, contact=own_contact)
    await start.got_contact(m, bot)

    async with pool().acquire() as conn:
        row = await conn.fetchrow("SELECT role FROM users WHERE telegram_id = $1", 1002)
    assert row is not None
    assert row["role"] == "admin"  # birinchi foydalanuvchi
    assert len(bot.calls) == 1


async def test_help_scopes_commands_by_role():
    await make_user("admin", 2001)
    await make_user("viewer", 2002)

    m_admin = FakeMessage(2001)
    await start.cmd_help(m_admin)
    admin_text = m_admin.answers[0]
    assert "/kurs" in admin_text
    assert "/boshlangich" in admin_text
    assert "/kirim" in admin_text

    m_viewer = FakeMessage(2002)
    await start.cmd_help(m_viewer)
    viewer_text = m_viewer.answers[0]
    assert "/kirim" not in viewer_text
    assert "/kurs" not in viewer_text
    assert "/balans" in viewer_text


async def test_help_requires_registration():
    m = FakeMessage(3001)
    await start.cmd_help(m)
    assert any("ro'yxatdan o'ting" in a for a in m.answers)
