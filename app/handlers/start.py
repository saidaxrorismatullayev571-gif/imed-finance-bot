from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BotCommand,
    BotCommandScopeChat,
    Message,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from app.db import acquire
from app.config import config

router = Router()

ROLE_LABEL = {"admin": "Administrator", "manager": "Menejer", "viewer": "Kuzatuvchi"}

COMMANDS_ALL = [
    BotCommand(command="balans", description="Kassa va fond balanslarini ko'rish"),
    BotCommand(command="dashboard", description="Web App dashboard ochish"),
    BotCommand(command="hisobot", description="Excel/PDF hisobot olish"),
    BotCommand(command="bekor", description="Joriy amalni bekor qilish"),
    BotCommand(command="yordam", description="Buyruqlar ro'yxati"),
]
COMMANDS_MANAGER_PLUS = [
    BotCommand(command="kirim", description="Daromad qayd etish"),
    BotCommand(command="chiqim", description="Xarajat qayd etish"),
    BotCommand(command="transfer", description="Kassalar orasida pul o'tkazish"),
]
COMMANDS_ADMIN_ONLY = [
    BotCommand(command="boshlangich", description="Kassaga boshlang'ich balans kiritish"),
    BotCommand(command="kurs", description="Valyuta kursini kiritish"),
    BotCommand(command="foydalanuvchilar", description="Foydalanuvchilar ro'yxati"),
    BotCommand(command="rol", description="Foydalanuvchi rolini o'zgartirish"),
    BotCommand(command="audit", description="So'nggi amallar jurnali"),
]


def _commands_for_role(role: str) -> list[BotCommand]:
    commands = list(COMMANDS_ALL)
    if role in ("admin", "manager"):
        commands = COMMANDS_MANAGER_PLUS + commands
    if role == "admin":
        commands = COMMANDS_ADMIN_ONLY + commands
    return commands


async def _apply_command_menu(bot: Bot, chat_id: int, role: str) -> None:
    await bot.set_my_commands(
        _commands_for_role(role), scope=BotCommandScopeChat(chat_id=chat_id)
    )


def contact_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot) -> None:
    async with acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, role FROM users WHERE telegram_id = $1", message.from_user.id
        )
    if user:
        await _apply_command_menu(bot, message.chat.id, user["role"])
        await message.answer(
            f"Salom, {message.from_user.full_name}! 👋\n"
            f"Rolingiz: {ROLE_LABEL.get(user['role'], user['role'])}.\n\n"
            "Buyruqlar ro'yxati uchun /yordam yuboring."
        )
        return

    await message.answer(
        "iMed Moliya botiga xush kelibsiz 👋\n\n"
        "Ro'yxatdan o'tish uchun telefon raqamingizni yuboring.",
        reply_markup=contact_kb(),
    )


@router.message(F.contact)
async def got_contact(message: Message, bot: Bot) -> None:
    if message.contact.user_id != message.from_user.id:
        await message.answer(
            "Faqat o'zingizning raqamingizni yuboring (\"📱 Raqamni yuborish\" tugmasi orqali)."
        )
        return

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

    await _apply_command_menu(bot, message.chat.id, role)
    await message.answer(
        f"Ro'yxatdan o'tdingiz ✅\nRolingiz: {ROLE_LABEL.get(role, role)}.\n\n"
        "Buyruqlar ro'yxati uchun /yordam yuboring.",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(Command("yordam"))
async def cmd_help(message: Message) -> None:
    async with acquire() as conn:
        user = await conn.fetchrow(
            "SELECT role FROM users WHERE telegram_id = $1 AND is_active", message.from_user.id
        )
    if user is None:
        await message.answer("Avval ro'yxatdan o'ting: /start")
        return

    lines = [f"📋 Buyruqlar ({ROLE_LABEL.get(user['role'], user['role'])}):"]
    for cmd in _commands_for_role(user["role"]):
        lines.append(f"/{cmd.command} — {cmd.description}")
    await message.answer("\n".join(lines))
