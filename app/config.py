import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    bot_token: str = os.environ.get("BOT_TOKEN", "")
    database_url: str = os.environ.get("DATABASE_URL", "")
    base_currency: str = os.getenv("BASE_CURRENCY", "UZS")
    admin_telegram_ids: tuple[int, ...] = field(
        default_factory=lambda: tuple(
            int(x) for x in os.getenv("ADMIN_TELEGRAM_IDS", "").split(",") if x.strip()
        )
    )
    # Web App dashboard uchun ochiq HTTPS manzil (masalan, sslip.io orqali).
    # Bo'sh bo'lsa — /dashboard buyrug'i "hali sozlanmagan" deb javob beradi
    # va ichki web-server umuman ishga tushmaydi.
    webapp_url: str = os.environ.get("WEBAPP_URL", "")
    webapp_port: int = int(os.getenv("WEBAPP_PORT", "8080"))


config = Config()
