"""Rejalashtirilgan vazifalar (APScheduler):

  • Kunlik CBU valyuta kursini olish (exchange_rates).
  • Kunlik qarz holatini yangilash (overdue) va muddati kelgan eslatmalarni yuborish.
"""
import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.db import acquire
from app.handlers.common import fmt_date, fmt_money
from app.services import fx

log = logging.getLogger("imed-finance-bot.scheduler")

TIMEZONE = "Asia/Tashkent"


async def job_fetch_fx() -> None:
    """Kunlik USD kursini CBU dan yangilaydi."""
    await fx.fetch_and_store_cbu()


async def job_debts(bot: Bot) -> None:
    """Muddati o'tgan qarzlarni 'overdue' qiladi va eslatmalarni yuboradi."""
    async with acquire() as conn:
        # 1) muddati o'tib, hali to'liq to'lanmagan qarzlar -> overdue
        await conn.execute(
            """UPDATE debts d SET status = 'overdue'
               WHERE d.due_date < CURRENT_DATE
                 AND d.status IN ('open', 'partial')
                 AND COALESCE(
                       (SELECT SUM(p.amount) FROM debt_payments p WHERE p.debt_id = d.id), 0
                     ) < d.principal"""
        )
        # 2) vaqti kelgan, hali yuborilmagan eslatmalar
        reminders = await conn.fetch(
            """SELECT r.id, d.direction, d.counterparty_name, d.due_date, d.currency,
                      d.principal, u.telegram_id,
                      COALESCE(
                          (SELECT SUM(p.amount) FROM debt_payments p WHERE p.debt_id = d.id), 0
                      ) AS paid
               FROM debt_reminders r
               JOIN debts d ON d.id = r.debt_id
               JOIN users u ON u.id = d.created_by
               WHERE r.is_sent = FALSE AND r.remind_at <= now()"""
        )

    for r in reminders:
        remaining = r["principal"] - r["paid"]
        if remaining > 0:
            if r["direction"] == "lent":
                text = (
                    f"⏰ <b>Qarz eslatmasi</b>\n\n"
                    f"{r['counterparty_name']} sizga {fmt_money(remaining, r['currency'])} qarzdor.\n"
                    f"Muddat: {fmt_date(r['due_date'])}."
                )
            else:
                text = (
                    f"⏰ <b>Qarz eslatmasi</b>\n\n"
                    f"Siz {r['counterparty_name']} ga {fmt_money(remaining, r['currency'])} "
                    f"qaytarishingiz kerak.\nMuddat: {fmt_date(r['due_date'])}."
                )
            try:
                await bot.send_message(r["telegram_id"], text)
            except Exception as exc:  # foydalanuvchi botni bloklagan bo'lishi mumkin
                log.warning("Eslatma yuborilmadi (tg=%s): %s", r["telegram_id"], exc)
        # yuborilgan (yoki allaqachon to'langan) deb belgilaymiz
        async with acquire() as conn:
            await conn.execute("UPDATE debt_reminders SET is_sent = TRUE WHERE id = $1", r["id"])


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Rejalashtiruvchini sozlaydi va ishga tushiradi."""
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(job_fetch_fx, "cron", hour=9, minute=0, id="fx_daily")
    scheduler.add_job(job_debts, "cron", hour=9, minute=5, args=[bot], id="debt_daily")
    scheduler.start()
    log.info("Scheduler ishga tushdi (FX + qarz eslatmalari)")
    return scheduler
