"""Bosqichli FSM oqimlari uchun umumiy yordamchilar (qadam ko'rsatkichi + tahrirlash).

Barcha oqimlar (kirim/chiqim/qarz/transfer/boshlang'ich) shu yordamchilarni qayta
ishlatadi — orqaga/tahrirlash/qadam mantig'i bitta joyda.

Multi-user (Faza 8) ga tayyor: hech qanday global/modul holati saqlanmaydi —
"tahrirlash rejimi" bayrog'i ham FSMContext ichida (har foydalanuvchiga xos).
"""
from aiogram.fsm.context import FSMContext

# Tasdiq ekranidan bitta maydonni tahrirlash bayrog'i (FSM data ichida saqlanadi).
_EDITING = "_editing"


def step_line(title: str, step: int, total: int) -> str:
    """Bosqich sarlavhasi: "<b>➕ Kirim</b>  ·  Qadam 2/5"."""
    return f"<b>{title}</b>  ·  Qadam {step}/{total}"


async def set_editing(state: FSMContext, on: bool) -> None:
    """Bitta maydonni tahrirlash rejimini yoqadi/o'chiradi.

    Yoqilgan bo'lsa, bosqich tugagach oddiy "keyingi bosqich" o'rniga tasdiqqa qaytamiz.
    """
    await state.update_data(**{_EDITING: on})


async def is_editing(state: FSMContext) -> bool:
    """Hozir tasdiqdan bitta maydon tahrirlanayaptimi?"""
    data = await state.get_data()
    return bool(data.get(_EDITING))
