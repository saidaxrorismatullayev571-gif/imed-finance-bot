"""Outer middleware'lar.

  • FSMResetMiddleware — FSM "qopqoni"ga qarshi: oqim o'rtasida asosiy menyu tugmasi
    bosilsa, oqim holatini tozalaydi (xabar "summa" deb o'qilmaydi).
  • AuthMiddleware — foydalanuvchini yuklaydi va yozish huquqini tekshiradi.

Rollar:
  • viewer  — faqat ko'rish (balans, hisobot)
  • manager — barcha moliyaviy amallar (kirim/chiqim/qarz/transfer/boshlang'ich)
  • admin   — hammasi + foydalanuvchilar va audit log (/admin)
"""
from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, TelegramObject

from app.handlers.common import get_current_user
from app.keyboards import (
    BTN_DEBT,
    BTN_EXPENSE,
    BTN_INCOME,
    BTN_OPENING,
    BTN_TRANSFER,
    MENU_BUTTONS,
)

# viewer uchun taqiqlangan (yozuvga olib boruvchi) menyu tugmalari
WRITE_BUTTONS = {BTN_INCOME, BTN_EXPENSE, BTN_DEBT, BTN_TRANSFER, BTN_OPENING}


class FSMResetMiddleware(BaseMiddleware):
    """Foydalanuvchi bosqichli oqim o'rtasida turib asosiy menyu tugmasini bossa,
    oqim holatini (state) tozalaydi. Shunda xabar joriy bosqich handleriga ("summa")
    emas, balki to'g'ri menyu entry-handleriga tushadi. Bu BARCHA oqimlarni birdan
    tuzatadi (har bir handlerda alohida tekshiruv shart emas).

    aiogram 3.x da FSMContextMiddleware update darajasida (outer) ishlagani uchun
    'state' va 'raw_state' shu message outer middleware'da allaqachon mavjud bo'ladi.
    """

    async def __call__(self, handler, event: TelegramObject, data: dict):
        if isinstance(event, Message) and event.text in MENU_BUTTONS:
            if data.get("raw_state") is not None:
                state: FSMContext | None = data.get("state")
                if state is not None:
                    await state.clear()
        return await handler(event, data)


class AuthMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        user = None
        from_user = getattr(event, "from_user", None)
        if from_user is not None:
            user = await get_current_user(from_user.id)
        data["user"] = user  # handlerlar ixtiyoriy ravishda ishlatishi mumkin

        # Yozish tugmasini viewer yoki ro'yxatdan o'tmagan bossa — to'xtatamiz
        if isinstance(event, Message) and event.text in WRITE_BUTTONS:
            if user is None:
                await event.answer("Avval /start orqali ro'yxatdan o'ting.")
                return None
            if user["role"] == "viewer":
                await event.answer("⛔️ Sizda yozish huquqi yo'q (rol: kuzatuvchi).")
                return None

        return await handler(event, data)
