"""Telegram WebApp initData tekshiruvi — Web App dashboard'ni faqat
haqiqiy Telegram mijozidan ochilgan sessiyaga ruxsat berish uchun.

Telegram hujjatlashtirilgan algoritm (https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app):
  1. 'hash' maydonini ajratib, qolgan maydonlarni alifbo tartibida
     "key=value\\n..." shaklida birlashtirish (data_check_string).
  2. secret_key = HMAC_SHA256(key=b"WebAppData", msg=bot_token)
  3. hisoblangan_hash = HMAC_SHA256(key=secret_key, msg=data_check_string)
  4. hisoblangan_hash 'hash' bilan bir xil bo'lsagina — haqiqiy.

Bot tokeni hech qachon kliyentga yuborilmaydi — bu tekshiruv faqat
serverda, initData ichidagi imzoni tasdiqlash uchun ishlatiladi."""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

MAX_AGE_SECONDS = 24 * 60 * 60  # 24 soatdan eski initData rad etiladi


def validate_init_data(init_data: str, bot_token: str, max_age: int = MAX_AGE_SECONDS) -> dict | None:
    """initData imzosi to'g'ri va muddati o'tmagan bo'lsa, parslangan
    lug'atni (jumladan 'user' — dict sifatida) qaytaradi. Aks holda None."""
    if not init_data or not bot_token:
        return None

    try:
        pairs = parse_qsl(init_data, strict_parsing=True)
    except ValueError:
        return None

    data = dict(pairs)
    received_hash = data.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None

    auth_date = data.get("auth_date")
    if auth_date is None or not auth_date.isdigit():
        return None
    if time.time() - int(auth_date) > max_age:
        return None

    if "user" in data:
        try:
            data["user"] = json.loads(data["user"])
        except (json.JSONDecodeError, TypeError):
            return None

    return data
