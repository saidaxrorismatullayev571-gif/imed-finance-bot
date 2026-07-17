from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from app.db import pool


class FakeUser:
    def __init__(self, uid, full_name="Test"):
        self.id = uid
        self.full_name = full_name


class FakeChat:
    def __init__(self, uid):
        self.id = uid


class FakeContact:
    def __init__(self, user_id, phone="+998900000000"):
        self.user_id = user_id
        self.phone_number = phone


class FakeCallbackMessage:
    def __init__(self):
        self.edits = []
        self.markups = []
        self.documents = []

    async def edit_text(self, text, reply_markup=None):
        self.edits.append(text)
        self.markups.append(reply_markup)

    async def answer_document(self, doc, caption=None):
        self.documents.append((doc, caption))


class FakeMessage:
    def __init__(self, uid, text=None, contact=None):
        self.from_user = FakeUser(uid)
        self.chat = FakeChat(uid)
        self.text = text
        self.contact = contact
        self.answers = []
        self.documents = []
        self.last_markup = None

    async def answer(self, text, reply_markup=None, parse_mode=None):
        self.answers.append(text)
        self.last_markup = reply_markup

    async def answer_document(self, doc, caption=None):
        self.documents.append((doc, caption))


class FakeCallback:
    def __init__(self, data, uid):
        self.data = data
        self.from_user = FakeUser(uid)
        self.message = FakeCallbackMessage()
        self.alerts = []

    async def answer(self, text=None, show_alert=False):
        if text:
            self.alerts.append((text, show_alert))


class FakeBot:
    def __init__(self):
        self.calls = []

    async def set_my_commands(self, commands, scope=None):
        self.calls.append((commands, scope))


def fsm_state(storage: MemoryStorage, uid: int) -> FSMContext:
    return FSMContext(storage=storage, key=StorageKey(bot_id=1, chat_id=uid, user_id=uid))


async def make_user(role: str, tg_id: int, phone: str = "+998900000000") -> int:
    async with pool().acquire() as conn:
        return await conn.fetchval(
            "INSERT INTO users (telegram_id, full_name, phone, role) VALUES ($1,'Test',$2,$3) RETURNING id",
            tg_id, phone, role,
        )


async def wallet_id(name: str = "Naqd UZS") -> int:
    async with pool().acquire() as conn:
        return await conn.fetchval("SELECT id FROM wallets WHERE name = $1", name)


async def income_source_id(name: str = "Kitob") -> int:
    async with pool().acquire() as conn:
        return await conn.fetchval("SELECT id FROM income_sources WHERE name = $1", name)


async def expense_category_id(name: str = "Ijara") -> int:
    async with pool().acquire() as conn:
        return await conn.fetchval("SELECT id FROM expense_categories WHERE name = $1", name)


async def wallet_balance(wid: int):
    async with pool().acquire() as conn:
        return await conn.fetchval("SELECT balance_uzs FROM v_wallet_balances WHERE wallet_id = $1", wid)
