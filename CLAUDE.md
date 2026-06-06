# CLAUDE.md — iMed Finance Bot (shaxsiy moliya boti)

Bu fayl Claude Code (va boshqa AI yordamchilar) uchun loyiha bo'yicha doimiy
yo'riqnoma. Har sessiyada o'qiladi. **Loyiha — SHAXSIY moliya boti** (korxona emas):
bitta foydalanuvchi o'z pulini, fondlarini, qarzlarini va kassalarini boshqaradi.

## 1. Arxitektura

| Qatlam | Texnologiya |
|---|---|
| Bot | Python 3.12 + aiogram 3.13 (async) |
| Baza | PostgreSQL 16 (ACID) |
| Reja | APScheduler (eslatma, CBU kursi) |
| Hosting | DigitalOcean (Docker Compose) |
| Hisobot | weasyprint (PDF), openpyxl (Excel) |
| Dashboard | Telegram Web App + FastAPI + Chart.js |

**Asosiy prinsip:** `transactions` jadvali — yagona, o'zgarmas (immutable) jurnal.
**Barcha** balanslar (kassa, fond, qarz) shundan **hisoblab** chiqariladi (view'lar),
hech qachon qo'lda saqlanmaydi. Shuning uchun balans hech qachon adashmaydi.

### Pul oqimi ishorasi (`signed_uzs` generated ustun, 001_init.sql)
Musbat (+): `opening`, `income`, `transfer_in`, `debt_in`
Manfiy (−): `expense`, `transfer_out`, `debt_out`, `debt_repay_out`

## 2. Kodbaza tuzilishi

```
app/
├── bot.py              # kirish nuqtasi, router'lar ulanadi
├── config.py           # .env (frozen dataclass `config`)
├── db.py               # asyncpg pool + acquire(actor_id) audit helper
├── keyboards.py        # main_menu_kb, choices_kb, confirm_kb
├── middlewares.py      # AuthMiddleware — rol/ruxsat tekshiruvi
├── handlers/
│   ├── common.py       # get_current_user, parse_amount/date, fmt_money/date, mask_phone
│   ├── start.py        # /start, onboarding, /cancel, /menu
│   ├── income.py       # kirim FSM      → kind='income'
│   ├── expense.py      # chiqim FSM     → kind='expense'
│   ├── balances.py     # balanslar + boshlang'ich balans (kind='opening')
│   ├── debt.py         # qarz (berish/olish/qaytarish/muddat/hisobot)
│   ├── transfer.py     # transfer (transfer_out/in juftligi)
│   ├── reports.py      # hisobotlar + Excel/PDF + Dashboard tugmasi
│   └── admin.py        # /admin — rollar + audit log (admin)
├── services/
│   ├── fx.py           # CBU valyuta kursi
│   ├── scheduler.py    # APScheduler (kurs + qarz eslatma/overdue)
│   └── export.py       # Excel (openpyxl) + PDF (weasyprint)
└── db/migrations/      # 001 sxema, 002 audit trigger, 003 seed
webapp/                 # Telegram Web App dashboard (FastAPI + Chart.js)
scripts/backup.sh       # kunlik pg_dump backup
tests/                  # pytest (sof yordamchilar)
```

## 3. Muhim konvensiyalar (BUZMANG)

- **Audit actor:** har bir yozuvni `async with acquire(actor_id=user_id) as conn:`
  ichida bajaring — bu `app.actor_id` ni o'rnatadi, audit trigger kim qilganini biladi.
  `created_by` ham doim shu `user_id` bo'lsin (transactions/debts NOT NULL).
- **Foydalanuvchi:** `from app.handlers.common import get_current_user` — telegram_id
  bo'yicha `users` (id, role, full_name) qaytaradi; ro'yxatdan o'tmagan bo'lsa `None`.
- **Summa:** `parse_amount(text) -> Decimal | None` (probel/vergulni tozalaydi, >0
  tekshiradi, 2 kasrga yaxlitlaydi). Hech qachon `float` ishlatmang — `Decimal`.
- **Formatlash:** `fmt_money(amount, currency)` → "1 234 567.00 UZS".
- **FSM:** har modul o'z `StatesGroup` va callback prefiksiga ega (inc/exp/opn/debt/trf).
  Callback format: `"{prefix}_{step}:{id}"`, bekor: `"{prefix}:cancel"`, tasdiq: `"{prefix}:ok"`.
- **Klaviatura:** ro'yxat tanlovlari `choices_kb(rows, prefix, extra=..., cancel=True)`.
  Tasdiq `confirm_kb(prefix)`. Reply menyu `main_menu_kb()`.
- **Parse mode:** bot HTML rejimida (`<b>` ishlatса bo'ladi).
- **Til:** butun UI o'zbek tilida (lotin). Apostrof uchun SQL'da `''`.
- **Valyuta enum:** asyncpg enum'ni `str` sifatida qabul qiladi ('UZS'/'USD').

## 4. Migratsiyalar
PostgreSQL konteyneri birinchi ishga tushishda `001 → 002 → 003` ni avtomatik bajaradi
(docker-entrypoint-initdb.d). Sxemani o'zgartirish kerak bo'lsa **yangi** migratsiya
fayli qo'shing (004, 005...) — eski fayllarni buzmang (ishlab turgan baza uchun).

## 5. Ishga tushirish / sinov
```bash
docker compose up -d --build
docker compose logs -f bot          # "Bot ishga tushdi (polling)"
```
Lokal Python yo'q bo'lsa, sintaksisni `docker compose build` (yoki konteyner ichida
`python -m py_compile`) bilan tekshiring.

---

# TZ → Implementatsiya rejasi (fazalar)

## ✅ Faza 0 — poydevor
Sxema, audit trigger, seed, onboarding (/start → kontakt → users). Birinchi user = admin.

## ✅ Faza 1 — kirim / chiqim / kassa / boshlang'ich balans
Asosiy menyu; income/expense/opening FSM oqimlari; balanslar `v_wallet_balances` +
`v_fund_balances` dan. (seed shaxsiy moliyaga moslangan: Jamg'arma/Kundalik/Zaxira/
Investitsiya fondlari; Oziq-ovqat/Transport/Uy-joy/... kategoriyalari.)

## ✅ Faza 2 — qarz + transfer + multi-valyuta
**Qarz (`handlers/debt.py`):**
- Yo'nalish: `lent` (qarz berdim) / `borrowed` (qarz oldim).
- Kiritish FSM: summa → kontragent ism → telefon → kassa → fond → muddat(due_date) →
  tasdiq. Yozadi: `debts` + `transactions` (lent→`debt_out`, borrowed→`debt_in`).
- Qaytarish (qisman/to'liq): `debt_payments` + `transactions`
  (lent qarz qaytib keldi→`debt_in`; borrowed qarzni qaytardim→`debt_repay_out`).
  Qoldiq `v_debt_outstanding` dan.
- Muddat uzaytirish (due_date UPDATE).
- Holat avtomatik: to'langan summaga qarab `open`/`partial`/`paid`; due_date o'tib
  ketsa va qoldiq bo'lsa `overdue`. Holatni hisoblovchi yordamchi yozing.
- Hisobot: faol qarzlar, bugun qaytadigan, "men qaytarishim kerak" (borrowed).
- Eslatma: `debt_reminders` + APScheduler; due_date bo'yicha xabar yuboriladi.

**Transfer (`handlers/transfer.py`):**
- Turlari: kassa→kassa, fond→fond, kassa+fond birga.
- `transfer_out` + `transfer_in` juftligi, ikkalasi bir xil `transfer_group_id` (UUID).
- UZS↔USD bo'lsa kurs bilan: chiqayotgan oyoq manba valyutasi, kelayotgan oyoq maqsad
  valyutasi; `fx_rate`/`amount_uzs` to'g'ri.

**Multi-valyuta (`services/fx.py`):**
- CBU API'dan (`https://cbu.uz/...`) UZS↔USD kursini olib `exchange_rates` ga saqlash.
- APScheduler kunlik yangilaydi. Tranzaksiyada `amount_uzs = amount * fx_rate`.
- So'nggi kursni o'qish: `exchange_rates` dan `fetched_at DESC LIMIT 1`.

**Biznes qoidalari (TZ 6):** fond balansi manfiyga ketsa **ogohlantirish** (bloklamaydi,
shaxsiy moliya); qarz holati avtomatik; kurs tarixi saqlanadi.

## ✅ Faza 3 — hisobotlar + dashboard
**Hisobot (`handlers/reports.py`):** P&L (oylik daromad/xarajat), kassa/fond qoldiqlari,
qarz hisoboti, transfer tarixi. PDF (weasyprint), Excel (openpyxl) eksport.
**Dashboard (`webapp/`):** Telegram Web App; kunlik/oylik grafik, fond pie, kassa
qoldiqlari, qarz portfeli. FastAPI (static + JSON API) + Chart.js, DigitalOcean.

## ✅ Faza 4 — xavfsizlik + test
Rollar (admin/manager/viewer) ruxsatlari; telefon maskirovka; audit log ko'rish (admin);
test holatlari (TZ 11) + README qabul mezonlari; backup (`pg_dump` cron); ekspert
tavsiyalari (TZ 12): inline tugmalar, calendar eslatma, smart kategoriya tavsiyasi.

## Ish uslubi
Har fazani alohida yozing, sintaksisni tekshiring, **alohida commit** qiling, qisqa
xulosa bering, keyin keyingisiga o'ting. Asosiy `transactions` prinsipini hech buzmang.
