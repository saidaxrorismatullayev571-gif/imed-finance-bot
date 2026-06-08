"""Kirim (daromad) qo'shish — bosqichli FSM oqimi (Faza 5 UX namunasi).

Oqim:  summa → daromad manbasi → kassa → fond → tasdiq → transactions(kind='income')

UX xususiyatlari (boshqa oqimlar uchun reference):
  • Har bosqichda qadam ko'rsatkichi ("Qadam 2/5").
  • Har bosqichda «⬅️ Orqaga» — oldingi bosqichga qaytadi, kiritilgan ma'lumot saqlanadi.
  • Tasdiq ekranida «✏️ Tahrirlash» — bitta maydonni tanlab, faqat shuni qayta kiritadi
    (boshidan boshlamaydi), so'ng tasdiqqa qaytadi.
  • Imkon qadar inline tugmalar (reply matn "summa" deb o'qilib qolmaydi).
  • /cancel, /menu, /start — doim ishlaydi; menyu tugmasi bosilsa FSMResetMiddleware
    state'ni tozalaydi.

Har bosqich `render_*` funksiyasiga ega — oldinga, orqaga va tahrirlash shulardan
qayta foydalanadi (takror kod yo'q). Saqlash `created_by`/`actor_id = user_id`
bilan (Faza 8 — multi-user — ga tayyor).
"""
from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.db import acquire
from app.handlers.common import fmt_money, get_current_user, parse_amount
from app.handlers.flow import is_editing, set_editing, step_line
from app.keyboards import (
    BTN_INCOME,
    choices_kb,
    confirm_kb,
    edit_fields_kb,
    main_menu_kb,
    nav_kb,
)

router = Router()

PREFIX = "inc"  # navigatsiya (back/cancel/ok/edit) uchun umumiy prefiks
TITLE = "➕ Kirim"
TOTAL = 5  # amount, source, wallet, fund, confirm

# Tasdiqdan tahrirlash mumkin bo'lgan maydonlar (ko'rinadigan matn, kalit)
EDIT_FIELDS = [
    ("💵 Summa", "amount"),
    ("🏷 Manba", "source"),
    ("👛 Kassa", "wallet"),
    ("🗂 Fond", "fund"),
]


class IncomeFSM(StatesGroup):
    amount = State()
    source = State()
    wallet = State()
    fund = State()
    confirm = State()


# =====================================================================
#  BOSQICHLARNI CHIZISH (render_*) — oldinga/orqaga/tahrirlash shulardan foydalanadi
# =====================================================================
async def render_amount(msg: Message, state: FSMContext, *, edit: bool) -> None:
    await state.set_state(IncomeFSM.amount)
    # 1-bosqich: «Orqaga» faqat tahrirlash rejimida ma'noli (tasdiqqa qaytaradi)
    back = await is_editing(state)
    text = step_line(TITLE, 1, TOTAL) + "\n\nKirim summasini kiriting (masalan: 1 500 000):"
    kb = nav_kb(PREFIX, back=back, cancel=True)
    await (msg.edit_text if edit else msg.answer)(text, reply_markup=kb)


async def render_source(msg: Message, state: FSMContext, *, edit: bool) -> None:
    async with acquire() as conn:
        # Smart tavsiya: ko'p ishlatilgan manbalar tepada
        sources = await conn.fetch(
            """SELECT s.id, s.name FROM income_sources s WHERE s.is_active
               ORDER BY (SELECT count(*) FROM transactions t
                         WHERE t.source_id = s.id AND t.kind = 'income') DESC, s.name"""
        )
    if not sources:
        await state.clear()
        await msg.answer("Daromad manbalari topilmadi. Administrator bilan bog'laning.")
        return
    await state.set_state(IncomeFSM.source)
    text = step_line(TITLE, 2, TOTAL) + "\n\nDaromad manbasini tanlang:"
    kb = choices_kb(sources, PREFIX + "_src", back=True, nav_prefix=PREFIX)
    await (msg.edit_text if edit else msg.answer)(text, reply_markup=kb)


async def render_wallet(msg: Message, state: FSMContext, *, edit: bool) -> None:
    async with acquire() as conn:
        wallets = await conn.fetch("SELECT id, name FROM wallets WHERE is_active ORDER BY name")
    await state.set_state(IncomeFSM.wallet)
    text = step_line(TITLE, 3, TOTAL) + "\n\nKassani tanlang:"
    kb = choices_kb(wallets, PREFIX + "_wal", back=True, nav_prefix=PREFIX)
    await (msg.edit_text if edit else msg.answer)(text, reply_markup=kb)


async def render_fund(msg: Message, state: FSMContext, *, edit: bool) -> None:
    async with acquire() as conn:
        funds = await conn.fetch("SELECT id, name FROM funds WHERE is_active ORDER BY name")
    await state.set_state(IncomeFSM.fund)
    text = step_line(TITLE, 4, TOTAL) + "\n\nFondni tanlang:"
    kb = choices_kb(
        funds, PREFIX + "_fund", extra=[("➖ Fondsiz", PREFIX + "_fund:none")],
        back=True, nav_prefix=PREFIX,
    )
    await (msg.edit_text if edit else msg.answer)(text, reply_markup=kb)


async def render_confirm(msg: Message, state: FSMContext, *, edit: bool) -> None:
    await state.set_state(IncomeFSM.confirm)
    data = await state.get_data()
    text = step_line(TITLE, 5, TOTAL) + "\n\n🧾 <b>Kirimni tasdiqlang</b>\n\n" + _summary(data)
    kb = confirm_kb(PREFIX, edit=True, back=True)
    await (msg.edit_text if edit else msg.answer)(text, reply_markup=kb)


# =====================================================================
#  1. BOSHLASH + SUMMA (matn kiritiladi)
# =====================================================================
@router.message(F.text == BTN_INCOME)
async def income_start(message: Message, state: FSMContext) -> None:
    user = await get_current_user(message.from_user.id)
    if not user:
        await message.answer("Avval /start orqali ro'yxatdan o'ting.")
        return
    await state.clear()
    await state.update_data(user_id=user["id"])  # Faza 8: amal egasi
    await render_amount(message, state, edit=False)


@router.message(IncomeFSM.amount)
async def income_amount(message: Message, state: FSMContext) -> None:
    amount = parse_amount(message.text)
    if amount is None:
        await message.answer("❗️ Noto'g'ri summa. Musbat raqam kiriting (masalan: 250000):")
        return
    await state.update_data(amount=str(amount))
    if await is_editing(state):
        await set_editing(state, False)
        await render_confirm(message, state, edit=False)
        return
    await render_source(message, state, edit=False)


# =====================================================================
#  2. DAROMAD MANBASI / 3. KASSA / 4. FOND (inline tanlov)
# =====================================================================
@router.callback_query(IncomeFSM.source, F.data.startswith(PREFIX + "_src:"))
async def income_source(call: CallbackQuery, state: FSMContext) -> None:
    async with acquire() as conn:
        src = await conn.fetchrow(
            "SELECT id, name FROM income_sources WHERE id = $1",
            int(call.data.split(":", 1)[1]),
        )
    await state.update_data(source_id=src["id"], source_name=src["name"])
    if await is_editing(state):
        await set_editing(state, False)
        await render_confirm(call.message, state, edit=True)
    else:
        await render_wallet(call.message, state, edit=True)
    await call.answer()


@router.callback_query(IncomeFSM.wallet, F.data.startswith(PREFIX + "_wal:"))
async def income_wallet(call: CallbackQuery, state: FSMContext) -> None:
    async with acquire() as conn:
        wal = await conn.fetchrow(
            "SELECT id, name, currency FROM wallets WHERE id = $1",
            int(call.data.split(":", 1)[1]),
        )
    await state.update_data(
        wallet_id=wal["id"], wallet_name=wal["name"], currency=wal["currency"]
    )
    if await is_editing(state):
        await set_editing(state, False)
        await render_confirm(call.message, state, edit=True)
    else:
        await render_fund(call.message, state, edit=True)
    await call.answer()


@router.callback_query(IncomeFSM.fund, F.data.startswith(PREFIX + "_fund:"))
async def income_fund(call: CallbackQuery, state: FSMContext) -> None:
    value = call.data.split(":", 1)[1]
    if value == "none":
        await state.update_data(fund_id=None, fund_name="—")
    else:
        async with acquire() as conn:
            fund = await conn.fetchrow("SELECT id, name FROM funds WHERE id = $1", int(value))
        await state.update_data(fund_id=fund["id"], fund_name=fund["name"])
    # Fond — oxirgi ma'lumot bosqichi; tahrir bo'lsa ham, bo'lmasa ham tasdiqqa o'tamiz
    await set_editing(state, False)
    await render_confirm(call.message, state, edit=True)
    await call.answer()


# =====================================================================
#  5. TASDIQ — saqlash / tahrirlash / orqaga
# =====================================================================
@router.callback_query(IncomeFSM.confirm, F.data.startswith(PREFIX + "_edit:"))
async def income_edit_field(call: CallbackQuery, state: FSMContext) -> None:
    """Tahrirlash uchun tanlangan maydonni qayta kiritishga o'tadi."""
    key = call.data.split(":", 1)[1]
    await set_editing(state, True)
    renderer = {
        "amount": render_amount,
        "source": render_source,
        "wallet": render_wallet,
        "fund": render_fund,
    }[key]
    await renderer(call.message, state, edit=True)
    await call.answer()


@router.callback_query(IncomeFSM.confirm, F.data.startswith(PREFIX + ":"))
async def income_confirm(call: CallbackQuery, state: FSMContext) -> None:
    action = call.data.split(":", 1)[1]
    if action == "edit":
        await call.message.edit_text(
            step_line(TITLE, 5, TOTAL) + "\n\n✏️ <b>Qaysi maydonni tahrirlaysiz?</b>",
            reply_markup=edit_fields_kb(PREFIX, EDIT_FIELDS),
        )
        await call.answer()
        return
    if action == "editcancel":
        await render_confirm(call.message, state, edit=True)
        await call.answer()
        return
    if action == "back":
        await render_fund(call.message, state, edit=True)
        await call.answer()
        return
    if action == "cancel":
        # Confirm bosqichida cancel shu handlerga tushadi (global cancel'dan oldin ro'yxatda)
        await _cancel(call, state)
        return
    if action != "ok":
        return

    data = await state.get_data()
    amount = Decimal(data["amount"])
    user_id = data["user_id"]
    async with acquire(actor_id=user_id) as conn:
        await conn.execute(
            """INSERT INTO transactions
                   (kind, wallet_id, fund_id, amount, currency, fx_rate, amount_uzs,
                    source_id, created_by)
               VALUES ('income', $1, $2, $3, $4, 1, $3, $5, $6)""",
            data["wallet_id"],
            data["fund_id"],
            amount,
            data["currency"],
            data["source_id"],
            user_id,
        )
    await state.clear()
    await call.message.edit_text("✅ Kirim saqlandi.\n\n" + _summary(data))
    await call.message.answer("Asosiy menyu:", reply_markup=main_menu_kb())
    await call.answer("Saqlandi")


# =====================================================================
#  NAVIGATSIYA: orqaga (har bosqich) + bekor (istalgan bosqich)
# =====================================================================
def _make_back(prev_render):
    """Bosqichdagi «⬅️ Orqaga» handlerini yasaydi.

    Tahrirlash rejimida — to'g'ridan-to'g'ri tasdiqqa qaytadi; aks holda oldingi
    bosqichni chizadi. prev_render=None bo'lsa (1-bosqich) — oqim bekor qilinadi.
    """
    async def handler(call: CallbackQuery, state: FSMContext) -> None:
        if await is_editing(state):
            await set_editing(state, False)
            await render_confirm(call.message, state, edit=True)
        elif prev_render is None:
            await _cancel(call, state)
        else:
            await prev_render(call.message, state, edit=True)
        await call.answer()

    return handler


router.callback_query.register(_make_back(None), IncomeFSM.amount, F.data == PREFIX + ":back")
router.callback_query.register(_make_back(render_amount), IncomeFSM.source, F.data == PREFIX + ":back")
router.callback_query.register(_make_back(render_source), IncomeFSM.wallet, F.data == PREFIX + ":back")
router.callback_query.register(_make_back(render_wallet), IncomeFSM.fund, F.data == PREFIX + ":back")


@router.callback_query(F.data == PREFIX + ":cancel")
async def income_cancel(call: CallbackQuery, state: FSMContext) -> None:
    await _cancel(call, state)


# =====================================================================
#  YORDAMCHILAR
# =====================================================================
def _summary(data: dict) -> str:
    return (
        f"Summa: <b>{fmt_money(data['amount'], data['currency'])}</b>\n"
        f"Manba: {data['source_name']}\n"
        f"Kassa: {data['wallet_name']}\n"
        f"Fond: {data['fund_name']}"
    )


async def _cancel(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text("❌ Bekor qilindi.")
    await call.message.answer("Asosiy menyu:", reply_markup=main_menu_kb())
    await call.answer()
