# iMed HR / Davomat botini YANGI KOMPANIYAGA 0 dan qurish — to'liq qo'llanma

> Bu hujjat ishlab turgan **iMed HR Davomat** tizimini boshqa bir kompaniya uchun
> noldan, aynan shunday qilib qurib berish bo'yicha **to'liq amaliy runbook**.
> Har bir qadam ketma-ket. "O'zgartiriladigan qiymatlar" jadvali (17-bo'lim) — eng muhim qism:
> faqat o'shalarni almashtirsangiz, qolgani bir xil ishlaydi.
>
> **Vaqt zonasi:** hamma joyda `Asia/Tashkent`. **Asosiy qoida:** NO HARD DELETE —
> hech narsa o'chirilmaydi, faqat `arxiv=true`.

---

## 0. Tizim nima qiladi (qisqacha)

Telegram bot orqali xodimlar har kuni **Keldi / Tushlikka / Qaytdi / Ketdi** tugmalarini
bosadi. Har "Keldi/Ketdi" da bot **lokatsiya** (ofisga yaqinlik) va **dumaloq video** (jonli isbot)
so'raydi. Ish vaqti 09:00–18:00 oynasi bo'yicha avtomatik hisoblanadi. Kunlik/haftalik/oylik
hisobotlar va maosh avtomatik chiqadi va Telegram guruhiga yuboriladi. Hammasi Postgres (Supabase)
da saqlanadi va zaxira sifatida Google Sheets'ga ham chiqariladi.

---

## 1. ARXITEKTURA

```
  Telegram  ──webhook(HTTPS)──►  Caddy (reverse-proxy, 443→8000)
                                      │
                                      ▼
                            Deno + grammY bot  (systemd: imed-hr-bot, :8000)
                                      │  (service_role kalit)
                                      ▼
                            Supabase  (Postgres)  ◄── yagona haqiqat manbai
                                      │
                          pg_cron (bazada) ──http──► Telegram API / bot
                                      │
                                      └──(ixtiyoriy)──► Google Sheets (zaxira/dalil)
```

| Qatlam | Texnologiya | Izoh |
|---|---|---|
| Bot | **Deno + grammY** (TypeScript) | bitta `index.ts` + `render.ts` + `excel.ts` + `pdf.ts` |
| Baza | **Supabase (PostgreSQL)** | barcha jadval/funksiya/view shu yerda |
| Rejalashtirish | **pg_cron** (bazada) | eslatma va avtomatik hisobotlar (node-cron EMAS) |
| HTTPS | **Caddy** (Docker yoki native) | avtomatik Let's Encrypt sertifikat |
| Server | **har qanday Linux VPS** | Ubuntu 22.04/24.04 tavsiya |
| Hisobot rasmlari | HTML → screenshot (`render.ts`) | chiroyli jadval rasm sifatida |
| Eksport | **exceljs** (.xlsx), **pdf-lib** (.pdf) | maosh/davomat varaqalari |

**Nega bunday:** javob < 0.3 soniya, limitsiz, deterministik hisob (maosh/soat SQL'da, AI'ga
ishonilmaydi), server qulasa ham pg_cron bazada ishlashda davom etadi.

---

## 2. KERAKLI NARSALAR (prerequisites)

Boshlashdan oldin shular bo'lsin:

1. **Telegram akkaunt** — bot yaratish uchun (@BotFather).
2. **Supabase akkaunt** — https://supabase.com (bepul reja ham yetadi boshida).
3. **Linux VPS** — Contabo / DigitalOcean / Hetzner. Minimal: 1 vCPU, 2 GB RAM.
   `root` yoki `sudo` huquqli foydalanuvchi.
4. **Domen yoki subdomen** — HTTPS webhook uchun (masalan `hrbot.firma.uz`
   yoki bepul `nip.io` / `duckdns.org`).
5. Serverda o'rnatiladi (skript o'zi qiladi): **Deno**, **Caddy**, **unzip**, **curl**.

---

## 3. QADAM 1 — Telegram bot yaratish

1. Telegramda **@BotFather** ni oching.
2. `/newbot` → bot nomi (masalan `Firma Davomat`) → username (masalan `firma_davomat_bot`).
3. BotFather sizga **BOT_TOKEN** beradi — `123456789:AA....` ko'rinishida. **Saqlab qo'ying.**
4. Tavsiya: `/setprivacy` → **Disable** (guruhda ishlashi kerak bo'lsa). Bizda bot faqat
   shaxsiy chatda ishlaydi, lekin hisobotni guruhga yuboradi — shuning uchun botni
   kerakli guruh(lar)ga **admin** qilib qo'shing.
5. Guruh va mavzu (topic) ID larini aniqlang:
   - Botni guruhga qo'shing, guruhga bitta xabar yozing.
   - `https://api.telegram.org/bot<TOKEN>/getUpdates` ni oching → `chat.id`
     (superguruh uchun `-100...` bilan boshlanadi) va forum bo'lsa `message_thread_id` ni oling.
   - Bularni **GROUP_CHAT_ID** va (forum bo'lsa) **GROUP_CHAT_ID_2 + GROUP_TOPIC_ID_2** sifatida saqlang.

> **Test bot:** Avval alohida **test tokeni** bilan qiling. Hammasi ishlagach, production tokenga o'ting.

---

## 4. QADAM 2 — Supabase loyiha + baza sxemasi

### 4.1 Loyiha yaratish
1. https://supabase.com → **New project**. Mintaqa: Yevropa (Frankfurt) — Toshkentga yaqinroq.
2. Kuchli **database password** qo'ying, saqlang.
3. Loyiha ochilgach: **Settings → API** dan oling:
   - **Project URL** — `https://<ref>.supabase.co`
   - **service_role** kaliti (maxfiy! faqat serverda) — bot shu bilan ulanadi.
   - **anon** kaliti — Google Sheets zaxira uchun (9-bo'lim).

### 4.2 Baza sxemasini qo'llash
Ikki yo'l bor:

**A) Tavsiya — mavjud iMed bazasidan to'liq nusxa (1:1 aynan shunday):**
Mavjud ishlaydigan loyihada barcha jadval/funksiya/cron bor. Ularning to'liq DDL sini
olib, yangi loyihaga qo'llang:
```bash
# Mavjud (reference) loyihadan sxema dump (faqat struktura):
supabase db dump --project-ref <ESKI_REF> --schema public -f schema_full.sql
# (yoki Supabase MCP / SQL Editor orqali har bir funksiya DDL sini export qiling)

# Yangi loyihaga qo'llash:
psql "postgresql://postgres:<PAROL>@db.<YANGI_REF>.supabase.co:5432/postgres" -f schema_full.sql
```

**B) Repozitoriydagi bazaviy sxemadan:**
Repo ichidagi `iMed_HR_Bot_v2_schema.sql` — poydevor (asosiy jadvallar + `imed_sof_min`).
Uni Supabase **SQL Editor** ga joylab **Run** bosing. Keyin 6-bo'limdagi qo'shimcha
obyektlarni (bolimlar, rollar, jurnal, hisobot/cron funksiyalari) qo'shing.

### 4.3 Kengaytmani yoqish
pg_cron va http (cron'dan Telegram'ga chaqiriq uchun) kerak. SQL Editor da:
```sql
create extension if not exists pg_cron;
create extension if not exists http;      -- yoki pg_net (loyihaga qarab)
```

---

## 5. QADAM 3 — Serverni tayyorlash (Deno + Caddy)

### 5.1 Deno o'rnatish
```bash
sudo apt-get update && sudo apt-get install -y unzip curl
curl -fsSL https://deno.land/install.sh | sh
sudo ln -sf ~/.deno/bin/deno /usr/local/bin/deno
deno --version
```

### 5.2 HTTPS (Caddy)
Agar serverda Caddy bo'lmasa, native o'rnating:
```bash
sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt-get update && sudo apt-get install -y caddy
```
`/etc/caddy/Caddyfile` ga domeningizni qo'shing (botni 8000-portga yo'naltiradi):
```
hrbot.firma.uz {
    reverse_proxy 127.0.0.1:8000
}
```
Keyin: `sudo systemctl reload caddy`

> Agar serverda allaqachon **Docker Caddy** (masalan `n8n-caddy-1`) ishlayotgan bo'lsa,
> 80/443-portlarni u egallagan bo'ladi. U holda o'sha Caddy konteynerining Caddyfile'iga
> domen bloki qo'shiladi va `reverse_proxy` manzili `172.18.0.1:8000` (host IP) bo'ladi.
> **Diqqat:** reboot'dan keyin nginx yoki boshqa narsa 80-portni o'g'irlamasin — bu bizda
> uzilishga sabab bo'lgan edi (16-bo'limga qarang).

---

## 6. QADAM 4 — Baza obyektlarining to'liq ro'yxati (nima bo'lishi shart)

Yangi baza quyidagilarni o'z ichiga olishi kerak. (Reference loyihadagi aynan shu obyektlar.)

### 6.1 Jadvallar (16 ta)
| Jadval | Vazifasi |
|---|---|
| `xodimlar` | Xodimlar (telegram_id, ism, bolim, rol, ish vaqti, arxiv) |
| `davomat` | Kunlik qatnashuv (keldi/tushlikka/qaytdi/ketdi, sof_min, lat/lng, video_file_id). **1 kun = 1 qator** |
| `bolimlar` | Bo'limlar (Sotuv / Boshqaruv / Marketing ...) — dinamik |
| `rollar` | Rollar va ularning **huquqlari** (menyu tugmalari) — dinamik |
| `sinov` | Sinov xodimlari (fixed umumiy summa, bosqich, natija) |
| `fix_kpi` | Kunlik KPI (qo'ng'iroq soni, gaplashish daqiqasi) |
| `qolda_baholar` | Oylik qo'lda baholar (CRM tozaligi %, sifat ball) |
| `bonus` | Bonuslar (summa, oy, sabab) |
| `tatil` | Ta'til/dam olish (tur, sana oralig'i, tasdiq holati) |
| `amocrm_calls` | AmoCRM qo'ng'iroqlari (keyin — integratsiya) |
| `amocrm_tasks` | AmoCRM vazifalari (keyin) |
| `config` | Sozlamalar/kursorlar (kalit→qiymat). Masalan `sheets_secret`, sync kursorlari |
| `jurnal` | Tizim jurnali (cron/webhook hodisalari, ogohlantirishlar) |
| `bot_sessiya` | grammY sessiya (step + jsonb data) — bot holati |
| `v_davomat_kun` (view) | Kunlik davomat + ism/rol |
| `v_oylik_soat` (view) | Oylik jami ish soati (har xodim) |

### 6.2 Funksiyalar (18 ta)
**Hisob:**
- `imed_sof_min(keldi,tushlikka,qaytdi,ketdi)` — **markaziy qoida.** 09:00–18:00 oynasi,
  erta kelish qo'shilmaydi, tushlik ayiriladi. Sof ish daqiqasini qaytaradi.
- `davomat_hisobla()` — trigger: har yozuvda `sof_min` ni avtomatik hisoblaydi.
- `set_updated_at()` — trigger: `updated_at` ni yangilaydi.
- `maosh_oylik(oy)` — oylik maoshni rol bo'yicha hisoblaydi (KPI pool / fix + ovqat + bonus).
- `davomat_oraliq(a,b)` / `oylik_davomat(oy)` — davr bo'yicha davomat yig'indisi.

**Avtomatik vazifalar (cron chaqiradi):**
- `avto_davomat()` — belgilangan xodimlarга (tugma bosmaydiganlar) to'liq kun yozadi.
- `tushlik_eslatma()`, `tushlik_qaytish_eslatma()`, `tushlik_nazorat()` — tushlik oqimi nazorati.
- `checkout_nazorat()` — ketishni unutganlarga eslatma.
- `soat10_hisobot()`, `kunlik_hisobot_yubor()` — kunlik hisobotlar guruhga.
- `haftalik_hisobot()` — dushanba haftalik.
- `oylik_yakunla()`, `oylik_davomat_hisobot()` — oy boshida yakuniy + arxiv.
- `anomaliya_tekshir()` — g'ayrioddiy holatlar signali.
- `webhook_salomatlik_tekshir()` — bot webhook'i sog'ligini tekshiradi (pending ko'paysa — DM ogohlantirish).

**Zaxira:**
- `hr_sheet_export(p_secret)` — Google Sheets zaxira uchun JSON (kunlik+oylik+maosh). 9-bo'lim.

### 6.3 pg_cron jadvali (13 ta) — vaqtlar **Toshkent** bo'yicha
> pg_cron **UTC** da ishlaydi. Toshkent = UTC+5. Quyida UTC ifoda → Toshkent vaqti.

| Job | Cron (UTC) | Toshkent | Nima qiladi |
|---|---|---|---|
| `keep-bot-warm` | `* * * * *` | har daqiqa | botni "uyg'oq" tutadi (cold-start yo'q) |
| `webhook-salomatlik` | `*/15 * * * *` | har 15 daq | webhook sog'ligi, muammo bo'lsa DM |
| `avto-davomat` | `5 4 * * 1-5` | 09:05 Du–Ju | avtomatik davomat (belgilangan kishilar) |
| `anomaliya-signal` | `35 4 * * 1-5` | 09:35 | anomaliya signali |
| `soat10-hisobot` | `0 5 * * 1-5` | 10:00 | ertalabki holat hisoboti |
| `tushlik-eslatma` | `30 8 * * 1-5` | 13:30 | tushlik eslatmasi |
| `tushlik-nazorat` | `5 9 * * 1-5` | 14:05 | tushlikdan qaytmaganlar |
| `tushlik-qaytish-eslatma` | `5 9 * * 1-5` | 14:05 | qaytish eslatmasi |
| `checkout-nazorat` | `30 13 * * 1-5` | 18:30 | ketishni unutganlar |
| `kunlik-hisobot` | `0 14 * * 1-5` | 19:00 | kunlik hisobot guruhga |
| `haftalik-hisobot` | `0 4 * * 1` | 09:00 Du | haftalik hisobot |
| `oylik-yakunlash` | `0 4 1 * *` | 09:00 (1-sana) | oyni yakunlash + arxiv |
| `oylik-davomat-hisobot` | `10 4 1 * *` | 09:10 (1-sana) | oylik davomat hisoboti |

Cron yaratishga misol (SQL Editor):
```sql
select cron.schedule('avto-davomat', '5 4 * * 1-5', $$ select avto_davomat(); $$);
select cron.schedule('kunlik-hisobot', '0 14 * * 1-5', $$ select kunlik_hisobot_yubor(); $$);
-- ... qolganlari ham shunday
```

---

## 7. QADAM 5 — Botni serverga o'rnatish (deploy)

Repo ichida tayyor deploy skript bor: **`ops/hr-bot/deploy-imed-hr-bot.sh`** (≈1500 qator).
U quyidagini o'zi qiladi:
1. Deno ni tekshiradi/o'rnatadi.
2. `/root/imed-hr-bot/` papkasida `index.ts`, `render.ts`, `excel.ts`, `pdf.ts` yaratadi.
3. Eski versiyani **zaxiralaydi** — yangi kod ishlamasa **avtomatik rollback** qiladi.
4. `.env` yozadi, **systemd** xizmati (`imed-hr-bot`) o'rnatadi, ishga tushiradi.
5. `http://localhost:8000` sog'lik tekshiruvi.

Qadamlar:
```bash
# 1) Repozitoriyni serverга oling
git clone <repo-url> /root/imed-src && cd /root/imed-src

# 2) Deploy skriptdagi/muhitdagi qiymatlarni YANGI kompaniya uchun almashtiring (17-bo'lim)
#    (BOT_TOKEN, SUPABASE_URL, SERVICE_KEY, GROUP IDs, ofis koordinatalari ...)

# 3) Skriptni ishga tushiring
bash ops/hr-bot/deploy-imed-hr-bot.sh
```

`.env` (server, `/root/imed-hr-bot/.env`) tarkibi:
```
BOT_TOKEN=<telegram token>
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_SERVICE_KEY=<service_role kaliti>     # MAXFIY — faqat serverda
GROUP_CHAT_ID=-100xxxxxxxxxx
GROUP_CHAT_ID_2=-100yyyyyyyyyy
GROUP_TOPIC_ID_2=3393
```

systemd buyruqlari:
```bash
sudo systemctl status imed-hr-bot      # holat
sudo journalctl -u imed-hr-bot -f      # loglar
sudo systemctl restart imed-hr-bot     # qayta ishga tushirish
```

---

## 8. QADAM 6 — Webhook'ni ulash

Bot HTTPS orqali ko'rinadigan bo'lgach (Caddy domeningizni 8000-portga ulagach):
```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=https://hrbot.firma.uz"
# tekshirish:
curl "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo"
```
`pending_update_count` 0 ga tushsa va `last_error_date` bo'sh bo'lsa — ulandi. ✅

---

## 9. QADAM 7 — Boshlang'ich ma'lumot (seed)

1. **Super admin:** `config` jadvaliga super admin telegram_id sini yozing (yoki birinchi
   `/start` bosgan kishini admin qiling — loyihaga qarab). Bu kishi "Xodimlar / Rollar / Sozlamalar"
   menyusini ko'radi.
2. **Bo'limlar:** bot menyusidan (yoki SQL) `bolimlar` ga qo'shing: Sotuv, Boshqaruv, Marketing...
3. **Rollar va huquqlar:** `rollar` ga rol qo'shib, har rolga qaysi tugmalar ko'rinishini belgilang
   (davomat, hisobot, xodim boshqaruvi, maosh...).
4. **Xodimlar:** har biriga ism + telegram_id + bo'lim + rol + ish vaqti. Xodim telegram_id sini
   bilish uchun u botga `/start` bossin yoki @userinfobot dan foydalaning.
5. **Avtomatik davomat ro'yxati:** tugma bosmaydigan (rahbar/belgilangan) xodimlarni
   `avto_davomat()` ichidagi ro'yxatga yoki config'ga qo'shing.

---

## 10. QADAM 8 — Google Sheets zaxira (ixtiyoriy, lekin tavsiya)

Barcha hisobot Google Sheets'da zaxira/dalil sifatida yuritiladi (moliyaviy + har xodimga isbot):
1. `hr_sheet_export(p_secret)` RPC bazada bo'lsin; `config.sheets_secret` ga maxfiy satr qo'ying;
   RPC ni **anon** rolga `grant execute` qiling (SECURITY DEFINER).
2. Bo'sh Google Sheet yarating.
3. **Extensions → Apps Script** ga repo/qo'llanmadagi sinxron skriptni joylang
   (`SUPABASE_URL`, `ANON_KEY`, `SECRET`, `SHEET_ID` ni yangi loyiha qiymatlari bilan).
4. `setup` funksiyasini bir marta **Run** qilib **Allow** bosing → varaq to'ladi va har kuni 21:00 da
   avtomatik yangilanadi (3 varaq: Kunlik jurnal / Oylik xulosa / Maosh).

> Eslatma: Google'ga yozish uchun bir martalik brauzer **Allow** sizning akkauntingizda bosilishi shart
> (Google xavfsizligi — buni dasturiy chetlab bo'lmaydi).

---

## 11. BIZNES QOIDALARI (har kompaniyaga sozlanadi)

Bu qiymatlarni yangi kompaniya siyosatiga moslang:

### 11.1 Ish vaqti (`imed_sof_min`)
- Oyna **09:00–18:00** (kerak bo'lsa funksiyadagi `ish_bosh`/`ish_tuga` ni o'zgartiring).
- Erta kelish hisoblanmaydi; kech kelsa haqiqiy vaqtdan; tushlik ayiriladi.
- Kunlik norma 8 soat, oylik 176 soat.

### 11.2 Ofis lokatsiyasi (`index.ts`)
- Koordinata: `40.385907, 71.786778`, radius `100 m` → yangi ofis koordinatasiga almashtiring.

### 11.3 Tushlik
- Faqat `12:00–14:00`, avtomatik 1 soat (yoki qaytdi−tushlikka, 90 daq+ bo'lsa 60 ga tushadi).

### 11.4 Maosh modeli
- **Sotuvchi:** KPI pool `4 000 000` (6 ko'rsatkich) + sotuv bonusi (pog'onali).
- **Rahbar/Marketolog:** `1 000 000` fix + ovqat (`40 000` × kelgan kun) + bonus.
- **Sinov:** butun davr uchun fixed summa (masalan `400 000`).
- Summalarни `maosh_oylik()` funksiyasida va `config` da moslang.

### 11.5 Avtomatik davomat xodimlar
- Reference'da: Himmatulloh, Arabboy, Saidaxror. Yangi kompaniya ro'yxatiga almashtiring.

---

## 12. KOD TUZILMASI (serverdagi `/root/imed-hr-bot/`)

| Fayl | Mazmuni |
|---|---|
| `index.ts` | Bosh fayl: grammY bot, barcha handlerlar (start, Keldi/Ketdi/Tushlik, lokatsiya, video_note, xodim/bo'lim/rol boshqaruvi, sinov, hisobot, maosh, sozlamalar), `Deno.serve` webhook |
| `render.ts` | HTML hisobot → rasm (chiroyli jadvallar, bo'lim bo'yicha guruhlash, gauge) |
| `excel.ts` | `.xlsx` eksport (exceljs): maosh, davomat (oraliq/kunlik) — rangli |
| `pdf.ts` | `.pdf` eksport (pdf-lib): maosh varaqasi |
| `.env` | Maxfiy sozlamalar (token, Supabase service key, guruh ID lari) |

Barcha DB kirish service_role kaliti bilan — RLS chetlab o'tiladi (shuning uchun RLS yoqilmagan;
agar anon kalit ishlatilsa, har jadvalga RLS + policy shart).

---

## 13. XAVFSIZLIK

- **service_role** kaliti **faqat serverda** (`.env`). Hech qachon kodga/gitga yozilmaydi.
- `.env` ni `.gitignore` ga qo'shing.
- Google Sheets uchun **anon** kaliti + `sheets_secret` ishlatiladi (service_role EMAS).
- NO HARD DELETE — har doim `arxiv=true`, tarix saqlanadi (audit uchun `created_at`/`updated_at`).
- Bot faqat shaxsiy chatда javob beradi (`if (chat.type !== 'private') return`).

---

## 14. TEST VA ISHGA TUSHIRISH (go-live)

1. **Test bot tokeni** bilan to'liq test: Keldi/Tushlik/Ketdi, lokatsiya rad holatlari,
   video_note isboti, kunlik hisobot, oylik maosh — hammasi.
2. Chegaraviy holatlar: ketmagan kun, kech kelish, tushliksiz kun, oy chegarasi, dam kunlari (shanba/yakshanba).
3. **Parallel** eski tizim bilan bir hafta solishtiring (agar eski tizim bo'lsa).
4. Ma'lumot import (eski Excel/Sheets → `xodimlar`, `davomat`).
5. **Production tokenga o'tish** (tunda): `.env` da token almashtiring → `restart` → `setWebhook`.
6. `getWebhookInfo` da `pending=0` ekanini tasdiqlang.

**Go-live checklist:**
- [ ] Supabase: 16 jadval + 18 funksiya + 13 cron bor
- [ ] `imed_sof_min` to'g'ri hisoblaydi (bir nechta holat tekshirilgan)
- [ ] Bot `systemctl status` → active, `localhost:8000` javob beradi
- [ ] `setWebhook` → `pending=0`
- [ ] Super admin menyuni ko'radi; oddiy xodim faqat davomat tugmalarini
- [ ] Kunlik hisobot guruhga/mavzuга boradi
- [ ] Google Sheets zaxira to'ladi (ixtiyoriy)
- [ ] webhook-salomatlik cron ishlayapti

---

## 15. MONITORING VA MUAMMOLARNI BARTARAF ETISH

(iMed tajribasidan — eng ko'p uchragan muammolar.)

| Belgisi | Sabab | Yechim |
|---|---|---|
| Telegram "Connection refused" | Caddy konteyneri qulagan | `docker start <caddy>` / `systemctl reload caddy` |
| "502 Bad Gateway" | Caddy noto'g'ri portga yo'naltiryapti | Caddyfile'da `reverse_proxy` manzilini (host:8000) tuzating |
| "404 Not Found" | reverse-proxy mavjud, lekin bot `/` ga javob bermaydi | to'g'ri xizmatga (bot) yo'naltiring |
| Reboot'dan keyin bot yo'q | nginx 80-portни o'g'irlagan | nginx'ni to'xtating/o'chiring, Caddy 80/443 ni olsin |
| `pending_update_count` o'sib ketgan | webhook uzilgan | `webhook-salomatlik` DM yuboradi; `setWebhook` qayta bosing |
| Hisobotда dam kuni hisoblanmagan | oylik funksiya faqat Du–Ju sanagan | `oylik_davomat_hisobot` da dam kunida kelgan ish ham qo'shilsin |

Foydali buyruqlar:
```bash
sudo journalctl -u imed-hr-bot -n 100 --no-pager   # oxirgi loglar
curl -s "https://api.telegram.org/bot<TOKEN>/getWebhookInfo" | jq   # webhook holati
# Supabase cron tarixi (SQL):
select * from cron.job_run_details order by start_time desc limit 20;
```

---

## 16. MA'LUMOTLARNI KO'CHIRISH (eski tizimdan)

Agar yangi kompaniyada allaqachon Excel/Sheets davomat bo'lsa:
1. CSV ga eksport qiling.
2. `xodimlar` ni avval to'ldiring (telegram_id lar bilan).
3. `davomat` ni import qiling (sana, keldi/ketdi vaqtlari) — `sof_min` trigger avtomatik hisoblaydi.
4. Bir nechta xodimда natijani eski tizim bilan solishtirib tekshiring.

---

## 17. ⭐ O'ZGARTIRILADIGAN QIYMATLAR — tez yo'riqnoma

Faqat shularni yangi kompaniya qiymatlari bilan almashtirsangiz, tizim aynan shunday ishlaydi:

| # | Qiymat | Qayerda | Misol (iMed) |
|---|---|---|---|
| 1 | `BOT_TOKEN` | `.env` | BotFather tokeni |
| 2 | `SUPABASE_URL` | `.env` | `https://<ref>.supabase.co` |
| 3 | `SUPABASE_SERVICE_KEY` | `.env` | service_role kaliti |
| 4 | `GROUP_CHAT_ID` | `.env` | `-1003966396343` |
| 5 | `GROUP_CHAT_ID_2` + `GROUP_TOPIC_ID_2` | `.env` | `-1003987794980` / `3393` |
| 6 | Ofis koordinatasi + radius | `index.ts` | `40.385907, 71.786778`, 100 m |
| 7 | Ish oynasi (09:00–18:00) | `imed_sof_min` (SQL) | 540–1080 daqiqa |
| 8 | Maosh summalari | `maosh_oylik` (SQL) + `config` | pool 4 mln, fix 1 mln, ovqat 40k |
| 9 | Avto-davomat ro'yxati | `avto_davomat` (SQL) | Himmatulloh, Arabboy, Saidaxror |
| 10 | Domen | Caddyfile | `hrbot.firma.uz` |
| 11 | `sheets_secret` + Sheet ID + anon key | `config` + Apps Script | zaxira uchun |
| 12 | Cron vaqtlari (kerak bo'lsa) | `cron.schedule` (SQL) | 6-bo'lim jadvali |

---

## 18. QURISH TARTIBI — eng qisqa ro'yxat

1. BotFather → **BOT_TOKEN** (3-bo'lim)
2. Supabase loyiha → sxema + pg_cron/http (4, 6-bo'lim)
3. VPS → Deno + Caddy + domen (5-bo'lim)
4. `.env` + 17-bo'lim qiymatlarини almashtir
5. `bash ops/hr-bot/deploy-imed-hr-bot.sh` (7-bo'lim)
6. `setWebhook` (8-bo'lim)
7. Super admin + bo'lim + rol + xodim seed (9-bo'lim)
8. pg_cron joblarini yoqish (6.3)
9. Google Sheets zaxira (10-bo'lim, ixtiyoriy)
10. Test → production tokenga o'tish (14-bo'lim)

---

*Manba fayllar (repo ichida): `iMed_HR_Bot_v2_schema.sql`, `iMed_HR_Bot_v2_TZ.md`,
`ops/hr-bot/deploy-imed-hr-bot.sh`, `CLAUDE.md`.*
