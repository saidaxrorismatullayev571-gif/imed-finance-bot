"""Web App dashboard'ni ochish tugmasi."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from app.config import config
from app.db import acquire
from app.handlers.finance import _get_user

router = Router()


@router.message(Command("dashboard"))
async def cmd_dashboard(message: Message) -> None:
    async with acquire() as conn:
        user = await _get_user(conn, message.from_user.id)
    if user is None:
        await message.answer("Avval ro'yxatdan o'ting: /start")
        return

    if not config.webapp_url:
        await message.answer(
            "Dashboard hali sozlanmagan (server tomonida WEBAPP_URL ko'rsatilmagan)."
        )
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Dashboardni ochish", web_app=WebAppInfo(url=config.webapp_url))]
        ]
    )
    await message.answer("Balans va so'nggi tranzaksiyalarni ko'rish:", reply_markup=kb)
