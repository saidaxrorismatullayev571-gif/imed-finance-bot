"""Sof (DB'siz) yordamchi funksiyalar uchun unit testlar.

Ishga tushirish:  pytest
"""
from datetime import date
from decimal import Decimal

import pytest

from app.handlers.common import fmt_date, fmt_money, mask_phone, parse_amount, parse_date


# --------------------------- parse_amount ---------------------------
@pytest.mark.parametrize("text, expected", [
    ("1000000", Decimal("1000000.00")),
    ("1 000 000", Decimal("1000000.00")),
    ("1,000,000", Decimal("1000000.00")),
    ("12.5", Decimal("12.50")),
    ("  250000  ", Decimal("250000.00")),
])
def test_parse_amount_valid(text, expected):
    assert parse_amount(text) == expected


@pytest.mark.parametrize("text", ["", "abc", "-5", "0", "0.00", None])
def test_parse_amount_invalid(text):
    assert parse_amount(text) is None


# --------------------------- parse_date / fmt_date ---------------------------
@pytest.mark.parametrize("text", ["30.06.2026", "2026-06-30", "30/06/2026", "30-06-2026"])
def test_parse_date_valid(text):
    assert parse_date(text) == date(2026, 6, 30)


@pytest.mark.parametrize("text", ["", "bad", "2026/13/40", None])
def test_parse_date_invalid(text):
    assert parse_date(text) is None


def test_fmt_date():
    assert fmt_date(date(2026, 6, 30)) == "30.06.2026"
    assert fmt_date(None) == "—"


# --------------------------- fmt_money ---------------------------
def test_fmt_money():
    assert fmt_money(Decimal("1234567.5"), "UZS") == "1 234 567.50 UZS"
    assert fmt_money(0, "UZS") == "0.00 UZS"
    assert fmt_money(Decimal("-5000"), "USD") == "-5 000.00 USD"


# --------------------------- mask_phone ---------------------------
def test_mask_phone():
    assert mask_phone("+998901234567") == "+998*****4567"
    assert mask_phone(None) == "—"
    assert mask_phone("") == "—"
    # qisqa raqam o'zgarmaydi
    assert mask_phone("12345") == "12345"
