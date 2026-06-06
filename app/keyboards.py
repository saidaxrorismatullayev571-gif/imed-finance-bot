"""Umumiy klaviaturalar (asosiy menyu + tanlov uchun inline tugmalar)."""
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

# --- Asosiy menyu tugmalari (matni handlerlarda filtr sifatida ishlatiladi) ---
BTN_INCOME = "➕ Kirim qo'shish"
BTN_EXPENSE = "➖ Chiqim qo'shish"
BTN_DEBT = "💳 Qarz"
BTN_TRANSFER = "🔄 Transfer"
BTN_BALANCES = "📊 Balanslar"
BTN_OPENING = "🏦 Boshlang'ich balans"


def main_menu_kb() -> ReplyKeyboardMarkup:
    """Ro'yxatdan o'tgan foydalanuvchi uchun doimiy asosiy menyu."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_INCOME), KeyboardButton(text=BTN_EXPENSE)],
            [KeyboardButton(text=BTN_DEBT), KeyboardButton(text=BTN_TRANSFER)],
            [KeyboardButton(text=BTN_BALANCES), KeyboardButton(text=BTN_OPENING)],
        ],
        resize_keyboard=True,
    )


def choices_kb(
    items: list,
    prefix: str,
    *,
    extra: list[tuple[str, str]] | None = None,
    cancel: bool = True,
) -> InlineKeyboardMarkup:
    """DB ro'yxatidan (id, name) inline tugmalar yasaydi.

    callback_data ko'rinishi: "{prefix}:{id}".
    extra — qo'shimcha tugmalar [(matn, callback_data), ...].
    cancel — pastda "Bekor qilish" tugmasini qo'shadi ("{prefix}:cancel").
    """
    rows = [
        [InlineKeyboardButton(text=row["name"], callback_data=f"{prefix}:{row['id']}")]
        for row in items
    ]
    if extra:
        rows.extend([[InlineKeyboardButton(text=text, callback_data=cb)] for text, cb in extra])
    if cancel:
        rows.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"{prefix}:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_kb(prefix: str) -> InlineKeyboardMarkup:
    """Tasdiq / bekor qilish tugmalari. callback: "{prefix}:ok" yoki "{prefix}:cancel"."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"{prefix}:ok"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"{prefix}:cancel"),
            ]
        ]
    )
