import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, ErrorEvent

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

    @dp.errors()
    async def global_error_handler(event: ErrorEvent) -> None:
        log.error("Kutilmagan xato: %s", event.exception, exc_info=event.exception)
        target = event.update.message or (
            event.update.callback_query.message if event.update.callback_query else None
        )
        if target is None:
            return
        try:
            await target.answer(
                "Kechirasiz, kutilmagan xatolik yuz berdi. /bekor bilan qaytadan urinib ko'ring."
            )
        except Exception:
            log.exception("Xato haqidagi xabarni ham yuborib bo'lmadi")

    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Ro'yxatdan o'tish"),
            BotCommand(command="yordam", description="Buyruqlar ro'yxati"),
        ]
    )

    log.info("Bot ishga tushdi (polling)")
    try:
        await dp.start_polling(bot)
    finally:
        await close_pool()
        log.info("To'xtatildi, ulanishlar yopildi")


if __name__ == "__main__":
    asyncio.run(main())
