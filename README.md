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

## Faza 2 — qarz + transfer + multi-valyuta

| Menyu | Imkoniyat |
|---|---|
| 💳 Qarz | berdim (`lent`)/oldim (`borrowed`), qaytarish (qisman/to'liq), muddat uzaytirish, faol qarzlar hisoboti |
| 🔄 Transfer | kassa→kassa, fond→fond, kassa+fond; `transfer_out`+`transfer_in` juftligi `transfer_group_id` bilan |

- **Qarz:** `debts` + `transactions` (`debt_out`/`debt_in`/`debt_repay_out`), to'lovlar
  `debt_payments` ga, qoldiq `v_debt_outstanding` dan. Holat avtomatik:
  `open`/`partial`/`paid`/`overdue`. Muddat bo'lsa `debt_reminders` ga eslatma yoziladi.
- **Multi-valyuta:** har tranzaksiyada `fx_rate` va `amount_uzs`. USD kursi CBU dan
  (`app/services/fx.py`) olinadi va `exchange_rates` ga saqlanadi. UZS↔USD transferda
  UZS qiymati saqlanib qoladi.
- **APScheduler** (`app/services/scheduler.py`): har kuni 09:00 da CBU kursini yangilaydi,
  09:05 da muddati o'tgan qarzlarni `overdue` qiladi va eslatmalarni yuboradi.
- **Audit tuzatildi:** `db.acquire` endi `app.actor_id` ni sessiya darajasida o'rnatadi,
  shu sababli ko'p oyoqli (transfer/qarz) yozuvlarda ham `actor_id` to'g'ri saqlanadi.

> ⚠️ Seed (`003_seed.sql`) faqat **bo'sh bazada** birinchi ishga tushishda bajariladi.
> Mavjud bazada yangilash kerak bo'lsa, `pgdata` hajmini tozalang yoki qo'lda `psql` bilan.

### Faza 2 — qabul mezoni (acceptance)

- [ ] Qarz berish/olish, qisman va to'liq qaytarish ishlaydi; qoldiq to'g'ri
- [ ] Qarz holati to'lov/muddatga qarab avtomatik o'zgaradi
- [ ] Transfer ikki oyoqli yoziladi, balanslar saqlanadi (UZS↔USD kurs bilan)
- [ ] CBU kursi `exchange_rates` ga tushadi; eslatmalar belgilangan vaqtda yuboriladi

## Faza 3 — hisobotlar + dashboard

**📈 Hisobotlar** (`app/handlers/reports.py`) menyusi:
- Matnli: P&L (oylik), balanslar, qarz hisoboti, transfer tarixi.
- 📥 **Excel** (openpyxl) — Tranzaksiyalar / P&L / Balanslar / Qarzlar varaqlari.
- 📄 **PDF** (weasyprint) — yig'ma hisobot. weasyprint mavjud bo'lmasa muloyim
  ogohlantiradi (bot yiqilmaydi).

**📈 Dashboard** — Telegram Web App (`webapp/`, FastAPI + Chart.js):
- `webapp/main.py` — `GET /api/summary` JSON (kassa/fond/pnl/kategoriya/qarz) + statik.
- `webapp/static/index.html` — oylik daromad-xarajat (line), fond taqsimoti (doughnut),
  kassa qoldiqlari (bar), xarajat kategoriyalari (bar).
- `docker-compose.yml` da `webapp` xizmati (8080-port). `.env` da `WEBAPP_URL` (HTTPS)
  o'rnatilsa, Hisobotlar menyusida «📈 Dashboard» tugmasi paydo bo'ladi.

> Dashboard tugmasi Telegram talabiga ko'ra **HTTPS** URL talab qiladi (reverse proxy
> yoki tunnel orqali). `WEBAPP_URL` bo'sh bo'lsa tugma ko'rsatilmaydi.

### Faza 3 — qabul mezoni (acceptance)

- [ ] Matnli hisobotlar (P&L, balanslar, qarz, transfer) to'g'ri ko'rsatiladi
- [ ] Excel va PDF eksport fayllari yuboriladi
- [ ] `webapp` xizmati `/api/summary` qaytaradi va dashboard grafiklarni chizadi

## Faza 4 — xavfsizlik + test + backup

**Rollar va ruxsatlar** (`app/middlewares.py`):

| Rol | Ruxsat |
|---|---|
| 👁 viewer | faqat ko'rish (balans, hisobot) |
| ✍️ manager | barcha moliyaviy amallar + ko'rish |
| 👑 admin | hammasi + `/admin` (foydalanuvchilar, audit log) |

- `AuthMiddleware` har update'da foydalanuvchini yuklaydi; viewer yozish tugmalarini
  bossa rad etiladi.
- **Admin panel** (`/admin`, `app/handlers/admin.py`): foydalanuvchilar ro'yxati
  (telefon **maskalangan**: `+998*****4567`), rol o'zgartirish (oxirgi adminni
  himoyalaydi), audit log (so'nggi 20 yozuv: kim, qachon, nima).
- **Telefon maskirovka:** `common.mask_phone` admin ko'rinishida qo'llanadi.

**Backup** (`scripts/backup.sh`, compose `backup` xizmati): kunlik `pg_dump`,
gzip, so'nggi 14 nusxa `./backups` da saqlanadi.

**Ekspert tavsiyalari (TZ 12):**
- Inline tugmalar — butun bot bo'ylab.
- «Calendar» eslatma — qarz muddati uchun tezkor sana tugmalari (+7/+14/+30 kun,
  oy oxiri, muddatsiz).
- Smart kategoriya/manba tavsiyasi — kirim/chiqimda ko'p ishlatilganlari tepada.

**Testlar:** sof yordamchilar uchun `pytest` (`tests/test_helpers.py`).
```bash
pip install -r requirements-dev.txt
pytest
```

### Faza 4 — test holatlari (TZ 11, qo'lda tekshirish)

1. **Rol:** viewer foydalanuvchi «➕ Kirim» bossa — «yozish huquqi yo'q» chiqadi.
2. **Admin:** admin `/admin` → foydalanuvchining rolini manager qiladi → endi u kirim qo'sha oladi.
3. **Oxirgi admin:** yagona adminni manager qilishga urinish — rad etiladi.
4. **Audit:** kirim qo'shilgach, `/admin → Audit log` da `INSERT transactions` ko'rinadi, actor to'g'ri.
5. **Backup:** `backup` xizmati ishlagach `./backups/imed_*.sql.gz` paydo bo'ladi.
6. **Smart tavsiya:** bir necha «Oziq-ovqat» chiqimdan keyin u ro'yxat tepasiga chiqadi.
7. **Qarz muddati:** «+30 kun» tugmasi muddatni 30 kundan keyin belgilaydi.

### Faza 4 — qabul mezoni (acceptance)

- [ ] viewer yoza olmaydi; manager/admin yoza oladi
- [ ] admin rollarni boshqaradi va audit logni ko'radi; telefon maskalangan
- [ ] oxirgi admin himoyalangan
- [ ] kunlik backup fayllari yaratiladi
- [ ] `pytest` yashil (sof yordamchilar test qoplamasi)
