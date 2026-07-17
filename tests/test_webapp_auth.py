import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from app.webapp_auth import validate_init_data

BOT_TOKEN = "123456:ABC-DEF"


def _make_init_data(fields: dict, token: str = BOT_TOKEN) -> str:
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    h = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": h})


def _fields(**overrides):
    base = {
        "query_id": "AAH123",
        "user": json.dumps({"id": 555, "first_name": "Test"}, separators=(",", ":")),
        "auth_date": str(int(time.time())),
    }
    base.update(overrides)
    return base


def test_valid_init_data_is_accepted_and_user_parsed():
    init_data = _make_init_data(_fields())
    result = validate_init_data(init_data, BOT_TOKEN)
    assert result is not None
    assert result["user"]["id"] == 555


def test_tampered_field_is_rejected():
    init_data = _make_init_data(_fields())
    tampered = init_data.replace("555", "999")
    assert validate_init_data(tampered, BOT_TOKEN) is None


def test_wrong_bot_token_is_rejected():
    init_data = _make_init_data(_fields())
    assert validate_init_data(init_data, "wrong-token") is None


def test_stale_auth_date_is_rejected():
    stale = _fields(auth_date=str(int(time.time()) - 999999))
    init_data = _make_init_data(stale)
    assert validate_init_data(init_data, BOT_TOKEN) is None


def test_missing_hash_is_rejected():
    assert validate_init_data("query_id=x&user=%7B%7D", BOT_TOKEN) is None


def test_empty_input_is_rejected():
    assert validate_init_data("", BOT_TOKEN) is None
    assert validate_init_data("something=1&hash=abc", "") is None
