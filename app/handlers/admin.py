"""Foydalanuvchi rollarini boshqarish + audit jurnalini ko'rish — Faza 4."""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.db import acquire
from app.handlers.finance import _get_user

router = Router()

ROLE_LABEL = {"admin": "Administrator", "manager": "Menejer", "viewer": "Kuzatuvchi"}
ROLES = ("admin", "manager", "viewer")
ACTION_LABEL = {"INSERT": "➕ qo'shildi", "UPDATE": "✏️ o'zgartirildi", "DELETE": "🗑️ o'chirildi"}


class ChangeRole(StatesGroup):
    choosing_user = State()
    choosing_role = State()


def _cancel_row() -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="rolecancel")]


async def _require_admin(message: Message, conn):
    user = await _get_user(conn, message.from_user.id)
    if user is None:
        await message.answer("Avval ro'yxatdan o'ting: /start")
        return None
    if user["role"] != "admin":
        await message.answer("Bu amalni faqat administrator bajara oladi.")
        return None
    return user


@router.message(Command("foydalanuvchilar"))
async def cmd_users(message: Message) -> None:
    async with acquire() as conn:
        admin = await _require_admin(message, conn)
        if admin is None:
            return
        users = await conn.fetch(
            "SELECT full_name, role, is_active FROM users ORDER BY created_at"
        )

    lines = ["👥 <b>Foydalanuvchilar</b>:"]
    for u in users:
        status = "" if u["is_active"] else " (faol emas)"
        lines.append(f"• {u['full_name']} — {ROLE_LABEL.get(u['role'], u['role'])}{status}")
    lines.append("\nRolni o'zgartirish uchun /rol yuboring.")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("rol"))
async def cmd_change_role(message: Message, state: FSMContext) -> None:
    async with acquire() as conn:
        admin = await _require_admin(message, conn)
        if admin is None:
            return
        users = await conn.fetch(
            "SELECT id, full_name, role FROM users WHERE is_active AND telegram_id != $1 "
            "ORDER BY full_name",
            message.from_user.id,
        )

    if not users:
        await message.answer("O'zgartirish uchun boshqa foydalanuvchi yo'q.")
        return

    rows = [
        [InlineKeyboardButton(
            text=f"{u['full_name']} ({ROLE_LABEL.get(u['role'], u['role'])})",
            callback_data=f"roleu:{u['id']}",
        )]
        for u in users
    ]
    rows.append(_cancel_row())
    await state.clear()
    await state.set_state(ChangeRole.choosing_user)
    await message.answer(
        "Kimning rolini o'zgartiramiz?", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )


@router.callback_query(ChangeRole.choosing_user, F.data.startswith("roleu:"))
async def cb_user_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = int(callback.data.split(":", 1)[1])
    async with acquire() as conn:
        target = await conn.fetchrow("SELECT id, full_name, role FROM users WHERE id = $1", user_id)
    if target is None:
        await callback.answer("Foydalanuvchi topilmadi.", show_alert=True)
        return

    await state.update_data(target_id=target["id"], target_name=target["full_name"])
    await state.set_state(ChangeRole.choosing_role)
    rows = [
        [InlineKeyboardButton(text=ROLE_LABEL[r], callback_data=f"roler:{r}")]
        for r in ROLES
        if r != target["role"]
    ]
    rows.append(_cancel_row())
    await callback.message.edit_text(
        f"{target['full_name']} — yangi rolni tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await callback.answer()


@router.callback_query(ChangeRole.choosing_role, F.data.startswith("roler:"))
async def cb_role_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    new_role = callback.data.split(":", 1)[1]
    if new_role not in ROLES:
        await callback.answer("Noto'g'ri rol.", show_alert=True)
        return

    data = await state.get_data()
    target_id = data["target_id"]
    target_name = data["target_name"]

    async with acquire() as conn:
        current_role = await conn.fetchval("SELECT role FROM users WHERE id = $1", target_id)
        if current_role == "admin" and new_role != "admin":
            admin_count = await conn.fetchval(
                "SELECT count(*) FROM users WHERE role = 'admin' AND is_active"
            )
            if admin_count <= 1:
                await callback.message.edit_text(
                    f"{target_name} — tizimning yagona administratori. "
                    "Avval boshqa birovni admin qiling, keyin buni o'zgartiring."
                )
                await state.clear()
                await callback.answer()
                return
        await conn.execute("UPDATE users SET role = $1 WHERE id = $2", new_role, target_id)

    await state.clear()
    await callback.message.edit_text(f"✅ {target_name} — yangi rol: {ROLE_LABEL[new_role]}")
    await callback.answer()


@router.callback_query(F.data == "rolecancel")
async def cb_role_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Bekor qilindi.")
    await callback.answer()


@router.message(Command("audit"))
async def cmd_audit(message: Message) -> None:
    async with acquire() as conn:
        admin = await _require_admin(message, conn)
        if admin is None:
            return
        rows = await conn.fetch(
            """SELECT a.created_at, u.full_name AS actor_name, a.action, a.entity_type, a.entity_id
               FROM audit_logs a
               LEFT JOIN users u ON u.id = a.actor_id
               ORDER BY a.created_at DESC
               LIMIT 20"""
        )

    if not rows:
        await message.answer("Audit jurnali hali bo'sh.")
        return

    lines = ["📜 <b>So'nggi amallar</b> (oxirgi 20 ta):"]
    for r in rows:
        who = r["actor_name"] or "noma'lum"
        when = r["created_at"].strftime("%d.%m %H:%M")
        action = ACTION_LABEL.get(r["action"], r["action"])
        lines.append(f"{when} — {who} — {r['entity_type']} #{r['entity_id']} {action}")
    await message.answer("\n".join(lines), parse_mode="HTML")
