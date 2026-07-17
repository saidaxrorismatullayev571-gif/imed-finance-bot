import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, ErrorEvent
from aiohttp import web

from app.config import config
from app.db import init_pool, close_pool
from app.handlers import admin, dashboard, finance, report, setup, start, transfer
from app.webapp import build_webapp

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
    dp.include_router(admin.router)
    dp.include_router(dashboard.router)
    # qarz (debt) funksiyasi so'ralmagani uchun hozircha qo'shilmadi

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

    webapp_runner: web.AppRunner | None = None
    if config.webapp_url:
        webapp_runner = web.AppRunner(build_webapp())
        await webapp_runner.setup()
        site = web.TCPSite(webapp_runner, "0.0.0.0", config.webapp_port)
        await site.start()
        log.info(
            "Web App dashboard ishga tushdi: 0.0.0.0:%s (tashqi: %s)",
            config.webapp_port, config.webapp_url,
        )
    else:
        log.info("WEBAPP_URL berilmagan — Web App dashboard o'chirilgan")

    log.info("Bot ishga tushdi (polling)")
    try:
        await dp.start_polling(bot)
    finally:
        if webapp_runner is not None:
            await webapp_runner.cleanup()
        await close_pool()
        log.info("To'xtatildi, ulanishlar yopildi")


if __name__ == "__main__":
    asyncio.run(main())
