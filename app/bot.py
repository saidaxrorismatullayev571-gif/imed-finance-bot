import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import config
from app.db import init_pool, close_pool
from app.handlers import finance, report, setup, start, transfer

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

    bot = Bot(token=config.bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start.router)
    dp.include_router(setup.router)
    dp.include_router(finance.router)
    dp.include_router(transfer.router)
    dp.include_router(report.router)
    # Keyingi: PDF hisobot + Web App dashboard (qarz — hozircha talab qilinmadi)

    log.info("Bot ishga tushdi (polling)")
    try:
        await dp.start_polling(bot)
    finally:
        await close_pool()
        log.info("To'xtatildi, ulanishlar yopildi")


if __name__ == "__main__":
    asyncio.run(main())
