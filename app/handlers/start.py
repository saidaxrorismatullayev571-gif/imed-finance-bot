from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from app.db import acquire
from app.config import config

router = Router()

ROLE_LABEL = {"admin": "Administrator", "manager": "Menejer", "viewer": "Kuzatuvchi"}


def contact_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    async with acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, role FROM users WHERE telegram_id = $1", message.from_user.id
        )
    if user:
        await message.answer(
            f"Salom, {message.from_user.full_name}! 👋\n"
            f"Rolingiz: {ROLE_LABEL.get(user['role'], user['role'])}.\n\n"
            "Asosiy menyu keyingi fazada qo'shiladi."
        )
        return

    await message.answer(
        "iMed Moliya botiga xush kelibsiz 👋\n\n"
        "Ro'yxatdan o'tish uchun telefon raqamingizni yuboring.",
        reply_markup=contact_kb(),
    )


@router.message(F.contact)
async def got_contact(message: Message) -> None:
    tg_id = message.from_user.id
    role = "admin" if tg_id in config.admin_telegram_ids else "viewer"

    async with acquire() as conn:
        # Tizimdagi birinchi foydalanuvchi avtomatik admin bo'ladi
        count = await conn.fetchval("SELECT count(*) FROM users")
        if count == 0:
            role = "admin"
        new_id = await conn.fetchval(
            """INSERT INTO users (telegram_id, full_name, phone, role)
               VALUES ($1, $2, $3, $4)
               ON CONFLICT (telegram_id) DO UPDATE SET full_name = EXCLUDED.full_name
               RETURNING id""",
            tg_id,
            message.from_user.full_name,
            message.contact.phone_number,
            role,
        )
        # audit log uchun actor o'rnatib qayta yozish (ixtiyoriy, namuna)
        await conn.execute("SELECT set_config('app.actor_id', $1, true)", str(new_id))

    await message.answer(
        f"Ro'yxatdan o'tdingiz ✅\nRolingiz: {ROLE_LABEL.get(role, role)}.",
        reply_markup=ReplyKeyboardRemove(),
    )
