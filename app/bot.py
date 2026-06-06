import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import config
from app.db import init_pool, close_pool
from app.handlers import admin, balances, debt, expense, income, reports, start, transfer
from app.middlewares import AuthMiddleware
from app.services.scheduler import setup_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("imed-finance-bot")


async def main() -> None:
    if not config.bot_token or not config.database_url:
        raise SystemExit("BOT_TOKEN va DATABASE_URL .env faylida ko'rsatilishi shart")

    await init_pool()
    log.info("Database pool ready")

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Auth: har bir update uchun foydalanuvchini yuklaydi va yozish huquqini tekshiradi
    # (outer_middleware — routing'dan oldin ishlaydi, barcha routerlarga ko'rinadi)
    auth = AuthMiddleware()
    dp.message.outer_middleware(auth)
    dp.callback_query.outer_middleware(auth)

    dp.include_router(start.router)
    dp.include_router(admin.router)
    dp.include_router(income.router)
    dp.include_router(expense.router)
    dp.include_router(debt.router)
    dp.include_router(transfer.router)
    dp.include_router(balances.router)
    dp.include_router(reports.router)

    scheduler = setup_scheduler(bot)

    log.info("Bot ishga tushdi (polling)")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await close_pool()
        log.info("To'xtatildi, ulanishlar yopildi")


if __name__ == "__main__":
    asyncio.run(main())
