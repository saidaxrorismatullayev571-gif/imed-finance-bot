# iMed Finance Bot

iMed Team uchun aqlli shaxsiy/biznes moliya va fondlarni boshqarish boti.
**Faza 0 — poydevor:** baza sxemasi, bot skeleti, ro'yxatdan o'tish (onboarding).

## Arxitektura

| Qatlam | Texnologiya |
|---|---|
| Bot | Python 3.12 + aiogram 3.x (async) |
| Baza | PostgreSQL 16 (ACID — pul hech qachon yo'qolmaydi) |
| Hosting | DigitalOcean (Docker Compose) |
| Reja | APScheduler (qarz eslatmalari, CBU kurslari — keyingi fazada) |

**Asosiy g'oya:** `transactions` jadvali — yagona o'zgarmas jurnal. Barcha balanslar
(kassa, fond, qarz) shundan **hisoblab** chiqariladi, hech qachon qo'lda saqlanmaydi.
Shuning uchun balans hech qachon adashmaydi.

## Loyiha tuzilishi

```
imed-finance-bot/
├── app/
│   ├── bot.py            # kirish nuqtasi
│   ├── config.py         # .env sozlamalari
│   ├── db.py             # asyncpg pool + audit actor helper
│   ├── handlers/
│   │   └── start.py      # /start, onboarding
│   └── db/migrations/
│       ├── 001_init.sql           # to'liq sxema + balans view'lari
│       ├── 002_audit_triggers.sql # audit log triggerlari
│       └── 003_seed.sql           # standart fond/kassa/kategoriyalar
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

## Ishga tushirish (DigitalOcean / har qanday Linux server)

1. **Repozitoriyni serverga yuklang** (yoki `git clone`).

2. **.env faylini yarating:**
   ```bash
   cp .env.example .env
   nano .env   # BOT_TOKEN va parolni kiriting
   ```
   - `BOT_TOKEN` — @BotFather dan oling
   - `DATABASE_URL` ichidagi parol `docker-compose.yml` dagi `POSTGRES_PASSWORD` bilan bir xil bo'lsin

3. **Ishga tushiring:**
   ```bash
   docker compose up -d --build
   ```
   Birinchi ishga tushishda PostgreSQL `001 → 002 → 003` migratsiyalarni avtomatik bajaradi.

4. **Tekshiring:**
   ```bash
   docker compose logs -f bot      # "Bot ishga tushdi (polling)" ko'rinishi kerak
   ```

5. **Telegram'da botingizga `/start` yuboring** → raqamingizni yuboring →
   ro'yxatdan o'tasiz. **Birinchi foydalanuvchi avtomatik admin** bo'ladi.

## Lokal sinov (Docker'siz)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# DATABASE_URL ni lokal Postgres'ga moslang, migratsiyalarni qo'lda bajaring:
psql "$DATABASE_URL" -f app/db/migrations/001_init.sql
psql "$DATABASE_URL" -f app/db/migrations/002_audit_triggers.sql
psql "$DATABASE_URL" -f app/db/migrations/003_seed.sql
python -m app.bot
```

## Keyingi fazalar

- **Faza 1:** daromad / xarajat / kassa / boshlang'ich balans — real moliya jurnali
- **Faza 2:** qarz to'liq (eslatma, qisman qaytarish, muddat) + transfer + multi-valyuta
- **Faza 3:** PDF/Excel hisobot + Web App dashboard + grafiklar
- **Faza 4:** rollar, audit ko'rinishi, testlar, backup, polish

## Faza 0 — qabul mezoni (acceptance)

- [ ] `docker compose up` xatosiz ishga tushadi
- [ ] 3 ta migratsiya bajarilgan (jadvallar, view'lar, triggerlar, seed mavjud)
- [ ] `/start` → raqam yuborish → foydalanuvchi `users` jadvaliga yoziladi
- [ ] Birinchi foydalanuvchi `admin` rolini oladi
- [ ] `SELECT * FROM v_wallet_balances;` 3 ta kassani 0 balans bilan ko'rsatadi

## Faza 1 — daromad / xarajat / kassa / boshlang'ich balans

Ro'yxatdan o'tgan foydalanuvchi `/start` (yoki `/menu`) yuborganda **asosiy menyu**
chiqadi. Barcha yozuvlar yagona `transactions` jurnaliga tushadi, balanslar esa
view'lardan **hisoblab** ko'rsatiladi.

| Menyu tugmasi | Oqim (aiogram FSM) | Natija |
|---|---|---|
| ➕ Kirim qo'shish | summa → daromad manbasi → kassa → fond → tasdiq | `kind='income'` |
| ➖ Chiqim qo'shish | summa → xarajat kategoriyasi → kassa → fond → tasdiq | `kind='expense'` |
| 🏦 Boshlang'ich balans | summa → kassa → fond → tasdiq | `kind='opening'` |
| 📊 Balanslar | — | `v_wallet_balances` + `v_fund_balances` |

- Har bir yozuvda `app.actor_id` o'rnatiladi (`db.acquire(actor_id=...)`), shu sababli
  audit triggerlari kim yozganini biladi; `created_by` ham shu foydalanuvchiga tegishli.
- Fond ixtiyoriy — oqimda "➖ Fondsiz" tugmasi `fund_id = NULL` qiladi.
- Istalgan bosqichda `/cancel` oqimni bekor qiladi.

**Handlerlar:** `app/handlers/income.py`, `expense.py`, `balances.py`
(boshlang'ich balans shu yerda). Umumiy klaviaturalar `app/keyboards.py` da,
yordamchilar (summa parser, formatlash, foydalanuvchi) `app/handlers/common.py` da.

### Faza 1 — qabul mezoni (acceptance)

- [ ] Ro'yxatdan o'tgan foydalanuvchiga asosiy menyu ko'rinadi
- [ ] Kirim/chiqim/boshlang'ich balans oqimlari to'liq ishlaydi va tasdiqlanadi
- [ ] Yozuvlar `transactions` ga to'g'ri `kind` bilan tushadi
- [ ] 📊 Balanslar kassa va fond qoldiqlarini hisoblab ko'rsatadi
- [ ] `audit_logs` da har yozuv uchun `actor_id` to'ldirilgan
