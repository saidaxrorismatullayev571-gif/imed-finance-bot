"""Umumiy klaviaturalar (asosiy menyu + bosqichli oqimlar uchun inline tugmalar).

Bu yerda barcha FSM oqimlari (kirim/chiqim/qarz/transfer/boshlang'ich) qayta
ishlatadigan navigatsiya tugmalari jamlangan:
  • choices_kb — ro'yxat tanlovi + ixtiyoriy «⬅️ Orqaga»/«❌ Bekor»
  • nav_kb     — matn kiritiladigan bosqich uchun faqat navigatsiya qatori
  • confirm_kb — tasdiq ekrani (Tasdiqlash + ixtiyoriy Tahrirlash/Orqaga)
  • edit_fields_kb — tasdiqdan qaysi maydonni tahrirlashni tanlash
"""
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
BTN_REPORTS = "📈 Hisobotlar"

# Barcha asosiy menyu tugmalari — FSMResetMiddleware oqim o'rtasida shulardan biri
# bosilganini aniqlab, state'ni tozalaydi (FSM "qopqoni"ga qarshi).
MENU_BUTTONS = {
    BTN_INCOME,
    BTN_EXPENSE,
    BTN_DEBT,
    BTN_TRANSFER,
    BTN_BALANCES,
    BTN_OPENING,
    BTN_REPORTS,
}


def main_menu_kb() -> ReplyKeyboardMarkup:
    """Ro'yxatdan o'tgan foydalanuvchi uchun doimiy asosiy menyu."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_INCOME), KeyboardButton(text=BTN_EXPENSE)],
            [KeyboardButton(text=BTN_DEBT), KeyboardButton(text=BTN_TRANSFER)],
            [KeyboardButton(text=BTN_BALANCES), KeyboardButton(text=BTN_OPENING)],
            [KeyboardButton(text=BTN_REPORTS)],
        ],
        resize_keyboard=True,
    )


# --------------------------- navigatsiya yordamchilari ---------------------------
def _nav_row(nav_prefix: str, *, back: bool, cancel: bool) -> list[InlineKeyboardButton]:
    """«⬅️ Orqaga» / «❌ Bekor qilish» tugmalari qatori (callback: nav_prefix:back/cancel)."""
    row: list[InlineKeyboardButton] = []
    if back:
        row.append(InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"{nav_prefix}:back"))
    if cancel:
        row.append(InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"{nav_prefix}:cancel"))
    return row


def nav_kb(nav_prefix: str, *, back: bool = False, cancel: bool = True) -> InlineKeyboardMarkup | None:
    """Matn kiritiladigan bosqich (masalan summa) uchun faqat navigatsiya qatori."""
    row = _nav_row(nav_prefix, back=back, cancel=cancel)
    return InlineKeyboardMarkup(inline_keyboard=[row]) if row else None


def choices_kb(
    items: list,
    prefix: str,
    *,
    extra: list[tuple[str, str]] | None = None,
    back: bool = False,
    cancel: bool = True,
    nav_prefix: str | None = None,
) -> InlineKeyboardMarkup:
    """DB ro'yxatidan (id, name) inline tugmalar yasaydi.

    callback_data ko'rinishi: "{prefix}:{id}".
    extra — qo'shimcha tugmalar [(matn, callback_data), ...].
    back/cancel — pastda «⬅️ Orqaga»/«❌ Bekor qilish» (callback: "{nav_prefix}:back/cancel").
    nav_prefix — navigatsiya tugmalari uchun alohida prefiks (sukut: prefix). Oqimning
      umumiy prefiksini bersangiz (masalan "inc"), orqaga/bekor bitta joyda boshqariladi.
    """
    nav_prefix = nav_prefix or prefix
    rows = [
        [InlineKeyboardButton(text=row["name"], callback_data=f"{prefix}:{row['id']}")]
        for row in items
    ]
    if extra:
        rows.extend([[InlineKeyboardButton(text=text, callback_data=cb)] for text, cb in extra])
    nav = _nav_row(nav_prefix, back=back, cancel=cancel)
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_kb(prefix: str, *, edit: bool = False, back: bool = False) -> InlineKeyboardMarkup:
    """Tasdiq ekrani tugmalari.

    callback: "{prefix}:ok" | "{prefix}:cancel" | "{prefix}:edit" | "{prefix}:back".
    edit/back berilmasa — eski (klassik) bir qatorli ko'rinish (Tasdiqlash + Bekor).
    """
    if not edit and not back:
        return InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"{prefix}:ok"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"{prefix}:cancel"),
            ]]
        )
    rows = [[InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"{prefix}:ok")]]
    second: list[InlineKeyboardButton] = []
    if edit:
        second.append(InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"{prefix}:edit"))
    if back:
        second.append(InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"{prefix}:back"))
    rows.append(second)
    rows.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"{prefix}:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def edit_fields_kb(prefix: str, fields: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """Tasdiqdan tahrirlash uchun maydon tanlash.

    fields — [(ko'rinadigan_matn, kalit), ...]; callback: "{prefix}_edit:{kalit}".
    Pastda «⬅️ Orqaga» (tasdiqqa qaytish) — callback: "{prefix}:editcancel".
    """
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"{prefix}_edit:{key}")]
        for label, key in fields
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"{prefix}:editcancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
