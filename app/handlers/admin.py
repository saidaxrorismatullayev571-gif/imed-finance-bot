"""Admin paneli (/admin) — faqat admin rol uchun.

  • 👥 Foydalanuvchilar: ro'yxat (telefon maskalangan), rol o'zgartirish.
  • 📜 Audit log: so'nggi yozuvlar (kim, qachon, nima qildi).
"""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.db import acquire
from app.handlers.common import mask_phone

router = Router()

ROLE_LABEL = {"admin": "👑 Admin", "manager": "✍️ Menejer", "viewer": "👁 Kuzatuvchi"}
ROLES = ("admin", "manager", "viewer")


def _is_admin(user) -> bool:
    return user is not None and user["role"] == "admin"


def _admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="adm:users")],
            [InlineKeyboardButton(text="📜 Audit log", callback_data="adm:audit")],
            [InlineKeyboardButton(text="❌ Yopish", callback_data="adm:close")],
        ]
    )


@router.message(Command("admin"))
async def admin_entry(message: Message, user=None) -> None:
    if not _is_admin(user):
        await message.answer("⛔️ Bu bo'lim faqat admin uchun.")
        return
    await message.answer("🛠 <b>Admin panel</b>", reply_markup=_admin_menu_kb())


@router.callback_query(F.data == "adm:close")
async def admin_close(call: CallbackQuery, user=None) -> None:
    await call.message.edit_text("Yopildi.")
    await call.answer()


@router.callback_query(F.data == "adm:users")
async def admin_users(call: CallbackQuery, user=None) -> None:
    if not _is_admin(user):
        await call.answer("⛔️ Faqat admin", show_alert=True)
        return
    async with acquire() as conn:
        users = await conn.fetch(
            "SELECT id, full_name, phone, role, is_active FROM users ORDER BY id"
        )
    rows = []
    for u in users:
        status = "" if u["is_active"] else " (faol emas)"
        rows.append([InlineKeyboardButton(
            text=f"{ROLE_LABEL.get(u['role'], u['role'])} · {u['full_name']} · "
                 f"{mask_phone(u['phone'])}{status}",
            callback_data=f"adm_urole:{u['id']}",
        )])
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm:back")])
    await call.message.edit_text(
        "👥 <b>Foydalanuvchilar</b>\nRolni o'zgartirish uchun tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await call.answer()


async def _render_roles(message: Message, uid: int) -> None:
    """Tanlangan foydalanuvchi uchun rol tugmalarini chizadi (joriy rol ✅ bilan)."""
    async with acquire() as conn:
        u = await conn.fetchrow("SELECT full_name, role FROM users WHERE id = $1", uid)
    rows = [[InlineKeyboardButton(
        text=("✅ " if r == u["role"] else "") + ROLE_LABEL[r],
        callback_data=f"adm_setrole:{uid}:{r}",
    )] for r in ROLES]
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm:users")])
    await message.edit_text(
        f"<b>{u['full_name']}</b> uchun yangi rolni tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data.startswith("adm_urole:"))
async def admin_pick_user(call: CallbackQuery, user=None) -> None:
    if not _is_admin(user):
        await call.answer("⛔️ Faqat admin", show_alert=True)
        return
    uid = int(call.data.split(":", 1)[1])
    await _render_roles(call.message, uid)
    await call.answer()


@router.callback_query(F.data.startswith("adm_setrole:"))
async def admin_set_role(call: CallbackQuery, user=None) -> None:
    if not _is_admin(user):
        await call.answer("⛔️ Faqat admin", show_alert=True)
        return
    _, uid, new_role = call.data.split(":")
    if new_role not in ROLES:
        await call.answer("Noto'g'ri rol", show_alert=True)
        return
    # O'zining adminligini tortib olishdan saqlanish: oxirgi adminni pasaytirmaymiz
    async with acquire(actor_id=user["id"]) as conn:
        if new_role != "admin":
            admin_count = await conn.fetchval(
                "SELECT count(*) FROM users WHERE role = 'admin' AND is_active"
            )
            target_is_admin = await conn.fetchval(
                "SELECT role = 'admin' FROM users WHERE id = $1", int(uid)
            )
            if target_is_admin and admin_count <= 1:
                await call.answer("⛔️ Oxirgi adminni pasaytirib bo'lmaydi", show_alert=True)
                return
        await conn.execute("UPDATE users SET role = $2 WHERE id = $1", int(uid), new_role)
    await call.answer("✅ Rol yangilandi")
    await _render_roles(call.message, int(uid))


@router.callback_query(F.data == "adm:back")
async def admin_back(call: CallbackQuery, user=None) -> None:
    await call.message.edit_text("🛠 <b>Admin panel</b>", reply_markup=_admin_menu_kb())
    await call.answer()


@router.callback_query(F.data == "adm:audit")
async def admin_audit(call: CallbackQuery, user=None) -> None:
    if not _is_admin(user):
        await call.answer("⛔️ Faqat admin", show_alert=True)
        return
    async with acquire() as conn:
        logs = await conn.fetch(
            """SELECT a.created_at, a.action, a.entity_type, a.entity_id, u.full_name AS actor
               FROM audit_logs a LEFT JOIN users u ON u.id = a.actor_id
               ORDER BY a.created_at DESC LIMIT 20"""
        )
    if not logs:
        text = "📜 Audit log bo'sh."
    else:
        lines = ["📜 <b>Audit log</b> (so'nggi 20)\n"]
        for r in logs:
            when = r["created_at"].strftime("%d.%m %H:%M")
            actor = r["actor"] or "—"
            lines.append(
                f"{when} · {r['action']} {r['entity_type']}#{r['entity_id']} · {actor}"
            )
        text = "\n".join(lines)
    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm:back")]]
        ),
    )
    await call.answer()
