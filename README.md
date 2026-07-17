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

## Buyruqlar

| Buyruq | Kim ishlata oladi | Vazifasi |
|---|---|---|
| `/start` | hamma | Ro'yxatdan o'tish / salomlashish |
| `/kirim` | admin, manager | Daromad qayd etish (kassa → manba → summa → izoh) |
| `/chiqim` | admin, manager | Xarajat qayd etish (kassa → kategoriya → summa → izoh) |
| `/boshlangich` | admin | Kassaga boshlang'ich balans yozish (`opening` tranzaksiya) |
| `/kurs` | admin | Valyuta kursini kiritish (1 USD = necha UZS) |
| `/transfer` | admin, manager | Kassalar orasida pul o'tkazish (hozircha bir xil valyuta ichida) |
| `/hisobot` | hamma (ro'yxatdan o'tgan) | Hisobot: davr (bugun/hafta/oy/hammasi) va format (Excel yoki PDF) tanlab, tranzaksiyalar + balanslarni oladi |
| `/balans` | hamma (ro'yxatdan o'tgan) | Barcha kassa va fond balanslarini ko'rsatadi |
| `/bekor` | hamma | Joriy kirim/chiqim qayd etish jarayonini bekor qiladi |
| `/yordam` | hamma (ro'yxatdan o'tgan) | Rolingizga mos buyruqlar ro'yxatini ko'rsatadi |
| `/foydalanuvchilar` | admin | Barcha foydalanuvchilar va ularning rollari ro'yxati |
| `/rol` | admin | Boshqa foydalanuvchining rolini o'zgartirish (admin/manager/viewer) |
| `/audit` | admin | So'nggi 20 ta amal (kim, qachon, nima o'zgartirdi) |
| `/dashboard` | hamma (ro'yxatdan o'tgan) | Web App: balans + so'nggi tranzaksiyalarni brauzer ko'rinishida ochish (WEBAPP_URL sozlangan bo'lsa) |

Ro'yxatdan o'tgandan so'ng Telegram'ning "/" menyu tugmasi ham rolingizga mos
buyruqlar bilan avtomatik to'ldiriladi.

USD (yoki UZS bo'lmagan) kassaga yozuv kiritish uchun avval `/kurs` bilan
kunlik kursni kiriting — kurs topilmasa bot yozuvni rad etadi (noto'g'ri
kursda balans buzilib qolmasligi uchun). Yangi kassa uchun ish boshidagi
mavjud pulni `/boshlangich` bilan bir marta kiriting.

## Web App dashboard (ixtiyoriy)

`/dashboard` buyrug'i Telegram ichida ochiladigan, faqat o'qish uchun
balans + so'nggi tranzaksiyalar sahifasini ko'rsatadi. Bu Telegram
WebApp texnologiyasi — Telegram **faqat HTTPS manzilni** ochadi, shuning
uchun oddiy `http://SERVER_IP` yetarli emas.

**Agar sizda domen yo'q, faqat server IP manzili bo'lsa** — bepul, DNS
sozlashsiz yechim [sslip.io](https://sslip.io) orqali:

1. Server IP manzilingizni toping (masalan `164.90.123.45`).
2. Nuqtalarni chiziqcha bilan almashtirib, oxiriga `.sslip.io` qo'shing:
   `164-90-123-45.sslip.io` — bu hostname avtomatik ravishda o'sha IP'ga
   yo'naltiradi (hech qanday DNS sozlash shart emas, darhol ishlaydi).
3. `.env` fayliga qo'shing:
   ```
   WEBAPP_URL=https://164-90-123-45.sslip.io
   ```
4. Serverda 80 va 443 portlari ochiq (firewall/Security Group) ekanini
   tekshiring — Let's Encrypt sertifikat olish uchun 80-port, HTTPS
   uchun 443-port kerak.
5. Caddy bilan birga ishga tushiring (bu servis Web App uchun avtomatik
   HTTPS sertifikat oladi va botga proksi qiladi):
   ```bash
   docker compose --profile webapp up -d --build
   ```
   (`--profile webapp` bo'lmasa Caddy umuman ishga tushmaydi — oddiy
   `docker compose up -d` avvalgidek faqat bot+bazani ko'taradi.)
6. Bir necha soniyadan so'ng `https://164-90-123-45.sslip.io` HTTPS
   bilan ochilishi kerak (Caddy sertifikatni birinchi so'rovda avtomatik
   oladi). Botda `/dashboard` yuboring — tugma chiqadi.

**Agar haqiqiy domeningiz bo'lsa** — xuddi shu qadamlar, faqat 2-bandda
domeningizni ko'rsating (`WEBAPP_URL=https://moliya.sizning-domen.uz`) va
domenning A-yozuvi server IP'ga yo'naltirilgan bo'lishi kerak.

**Xavfsizlik:** dashboard sahifasi ochiq URL bo'lsa ham, `/api/dashboard`
so'rovi har safar Telegram'ning `initData` imzosini (HMAC-SHA256, bot
tokeningiz bilan) tekshiradi — faqat haqiqiy Telegram mijozidan, sizning
botingizga ro'yxatdan o'tgan foydalanuvchi nomidan kelgan so'rovlargina
ma'lumot oladi. Dashboard **faqat o'qish uchun** — pul kiritish/o'zgartirish
hali ham botning o'zida (`/kirim`, `/chiqim` va h.k.).

## Zaxira nusxalash (backup)

Bu bot pul hisobini yuritadi — baza yo'qolishi butun moliyaviy tarixni
yo'qotish degani. Shuning uchun serverda **kunlik avtomatik zaxira** shart:

```bash
# Qo'lda sinab ko'rish (server ichida, docker compose ishlab turganda):
./scripts/backup.sh
# -> ./backups/imed_finance_<sana>.sql.gz yaratiladi, 30 kundan eskilari o'chiriladi
```

**DigitalOcean droplet'da cron orqali kunlik avtomatlashtirish:**

```bash
crontab -e
# Har kuni soat 03:00 da:
0 3 * * * cd /path/to/imed-finance-bot && ./scripts/backup.sh >> /var/log/imed-backup.log 2>&1
```

Zaxiralarni serverdan tashqariga ham ko'chirish tavsiya etiladi (masalan,
`rclone`/`scp` bilan boshqa joyga) — faqat shu serverda saqlash "server
o'chsa hammasi yo'qoladi" degani.

**Tiklash** (falokat holatida, DIQQAT — joriy ma'lumotni butunlay
almashtiradi):

```bash
./scripts/restore.sh backups/imed_finance_20260717_030000.sql.gz
```

`backups/` papkasi `.gitignore`da — real moliyaviy ma'lumot hech qachon
Git'ga tushmaydi.

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

## Testlar

```bash
pip install -r requirements-dev.txt
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/imed_finance_test"
export BOT_TOKEN="123:test"
createdb imed_finance_test   # yoki: psql -c "CREATE DATABASE imed_finance_test;"
psql "$DATABASE_URL" -f app/db/migrations/001_init.sql
psql "$DATABASE_URL" -f app/db/migrations/002_audit_triggers.sql
psql "$DATABASE_URL" -f app/db/migrations/003_seed.sql
pytest -v
```

Har bir push/PR'da GitHub Actions (`.github/workflows/ci.yml`) shu testlarni
avtomatik ishga tushiradi (Postgres 16 service konteyneri bilan).

## Keyingi fazalar

- ✅ ~~**Faza 1:** daromad / xarajat / kassa / boshlang'ich balans — real moliya jurnali~~
  (`/kirim`, `/chiqim`, `/boshlangich`, `/kurs`, `/balans`)
- **Faza 2 (davom etmoqda):** ✅ kassalar orasida transfer (`/transfer`, bir xil valyuta ichida)
  — qarz funksiyasi so'ralmagani uchun hozircha o'tkazib yuborildi
- ✅ ~~**Faza 3:** PDF/Excel hisobot + Web App dashboard + grafiklar~~
  (`/hisobot` — davr + format (Excel/PDF) tanlanadi; `/dashboard` — Web App,
  sslip.io orqali domensiz HTTPS bilan ham ishlaydi, README'da to'liq qadamlar)
- ✅ ~~**Faza 4:** rollar, audit ko'rinishi, testlar, backup, polish~~
  (`/foydalanuvchilar`, `/rol`, `/audit`, pytest — 47 ta, CI'da avtomatik,
  `scripts/backup.sh` + `restore.sh`)

## Faza 0 — qabul mezoni (acceptance)

- [ ] `docker compose up` xatosiz ishga tushadi
- [ ] 3 ta migratsiya bajarilgan (jadvallar, view'lar, triggerlar, seed mavjud)
- [ ] `/start` → raqam yuborish → foydalanuvchi `users` jadvaliga yoziladi
- [ ] Birinchi foydalanuvchi `admin` rolini oladi
- [ ] `SELECT * FROM v_wallet_balances;` 3 ta kassani 0 balans bilan ko'rsatadi
