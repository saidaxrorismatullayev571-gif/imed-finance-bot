# CLAUDE.md — iMed HR/Davomat Bot v2

> Bu fayl Claude Code uchun **build konteksti**. Har ishни shu qoidalarga rioya qilib bajar.
> Batafsil funksiyalar: `iMed_HR_Bot_v2_TZ.md`. Ma'lumotlar bazasi: `iMed_HR_Bot_v2_schema.sql`.

---

## 0. MUHIM GUARDRAILS (hech qachon buzma)
- **Eski botga TEGMA.** Eski Google Apps Script davomat boti ishlab turibdi — u zaxira.
- **Avval TEST bot tokeni** bilan ishla. Production tokenga faqat to'liq test tugagach o'tiladi.
- **NO HARD DELETE** — hech narsa o'chirilmaydi, `arxiv=true` qilinadi.
- **service_role kalit faqat serverda** (env). Hech qachon kodga/gitga yozma.
- Har fazани tugatib, **test qilmasdan** keyingisiga o'tma.

---

## 1. LOYIHA
iMed Team (tibbiy ta'lim biznesi, ~15 xodim) uchun Telegram HR/davomat boti.
Maqsad: eski sekin Apps Script tizimini tez, avtomatik Supabase tizimiga ko'chirish.

## 2. STACK
- **Til:** TypeScript (strict)
- **Bot:** grammY
- **Baza:** Supabase (Postgres)
- **Server:** DigitalOcean (Node.js)
- **Cron:** node-cron (bot ichida, server bilan bitta joyda)
- **Repo:** GitHub (private)

## 3. CONNECTORLARDAN MAKSIMAL FOYDALANISH
Ishni tezlashtirish uchun MCP connectorlarни faol ishlat:
- **Supabase MCP** ⭐ — loyiha ma'lumotini olish, `schema.sql`ни migratsiya sifatida qo'llash,
  jadval/funksiya yaratish, dev vaqtida query, **TypeScript tiplar generatsiyasi**
  (`generate_typescript_types`), edge functions. SQL'ni qo'lда pastyat qilma — MCP orqali qo'lla.
- **GitHub** — repo boshqaruv, commit, branch (nativ git).
- **Notion** — TZ/progress tracker yangilab borish (ixtiyoriy).
- Ish boshlashдан oldin: kerakli connector ulanganini tekshir; ulanmagan bo'lsa, foydalanuvchiga ayt.
- **n8n ISHLATILMAYDI** — barcha cron/scheduled ishlar bot ichida node-cron bilan.

## 4. ARXITEKTURA QOIDALARI
- Modulli: `handlers/`, `services/`, `db/`, `cron/`, `utils/`, `config/`.
- grammY session — Supabase `bot_sessiya` jadvalida (yoki grammY session + Supabase adapter).
- Barcha DB kirish — bitta `db` service orqali (to'g'ridan query tarqatma).
- Env: `BOT_TOKEN`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `GROUP_CHAT_ID`, `GROUP_CHAT_ID_2`, `GROUP_TOPIC_ID_2`.

---

## 5. BIZNES QOIDALARI (aniq — kod shu bo'yicha)

### 5.1 Faqat SHAXSIY chat
Bot **faqat private chatда** ishlaydi. Guruh/superguruh/forum ichidagi xabarlarга
UMUMAN javob berma (`if (chat.type !== 'private') return`). Guruhга faqat davomat
XULOSALARI dastur tomonidan yuboriladi.

### 5.2 Xabar yo'naltirish (xulosalar)
Davomat xulosasi FAQAT 2 joyga:
1. Eski guruh: `GROUP_CHAT_ID` (-1003966396343)
2. Forum guruh: `GROUP_CHAT_ID_2` (-1003987794980), **`message_thread_id = 3393`** (Davomat bo'limi)
Boshqa hech qayerga (Umumiy suhbat va h.k.) yuborma.

### 5.3 Davomat oqimi
Keldi/Tushlikka/Ketdi tugmalari (shaxsiy chatда). Keldi/Ketdi uchun:
1. Lokatsiya so'ra (ofis 40.385907, 71.786778, radius 100 m).
2. Forward/eski lokatsiya (90 s+) → rad.
3. **Lokatsiyadан so'ng DUMALOQ VIDEO (video_note) so'ra** — majburiy isbot.
   Forward qilingan video_note → rad. Faqшu ikkisi bo'lgach qayd etiladi.
Tushlik: faqat 12:00–14:00, avtomatik 1 soat + qaytish vaqti.

### 5.4 Ish vaqti hisobi (markaziy funksiya `imed_sof_min`)
- Oyna **09:00–18:00**.
- 09:00 dan ERTA kelsa → 09:00 dan (ortiqcha HISOBLANMAYDI).
- 09:00 dan KECH kelsa → haqiqiy kech vaqtdan.
- Ketmasa/18:00 dan kech ketsa → 18:00; erta ketsa → haqiqiy vaqt.
- Tushlik (odatda 1 soat) ayriladi. Kunlik norma 8 soat, oylik 176 soat.
- Bu funksiya `schema.sql`да Postgres funksiyasi sifatida bor — DB'да hisobla.

### 5.5 Avtomatik davomat (belgilangan xodimlar)
Ro'yxat: **Himmatulloh, Arabboy, Saidaxror** (ism bo'yicha moslash). Ular Start/tugma
bosmaydi. Har ish kuni 09:05 da to'liq kun (09:00–18:00, 8 soat, "Avtomatik") yoziladi.
Guruhга xabar YUBORILMAYDI (jim). Bugungi yozuv bo'lsa qayta yozma.

### 5.6 Maosh modeli
**Sotuvchi = KPI pool 4 000 000 + Sotuv bonusi**
KPI (6): ish vaqti(176s)=1.5M, chiquvchi qo'ng'iroq(2200)=600k, gaplashish(3960min)=600k,
qayta aloqa(90%)=300k, CRM tozaligi(95%)=500k, qo'ng'iroq sifati(85)=500k.
Har biri = min(haqiqiy/norma,1) × summa.
> HOZIRCHA: qo'ng'iroq/gaplashish/qayta aloqa **qo'lда kiritiladi** (AmoCRM keyin).
Sotuv bonusi (pog'onali, keyin yoqiladi): 70M→3%, 100M→5%, 120M→5%+150k, 150M→5%+300k, 200M→5%+600k.
**Rahbar/Marketolog:** 1 000 000 fix + ovqat(40 000 × kelgan kun) + bonus.
**Yakuniy = maosh + ovqat + bonus.** (Avans/jarima YO'Q — olib tashlangan.)

### 5.7 Sinov
Butun sinov davri uchun **fixed umumiy summa** (masalan 400 000, bir marta). Bosqich:
Adaptatsiya (1–3 kun) → Sinov+Imtihon (max 15 kun). Natija: Qabul/Rad/Uzaytirish.

---

## 6. MA'LUMOTLAR BAZASI
`schema.sql`ni Supabase MCP orqali migratsiya qilib qo'lla. Jadvallar: `xodimlar, davomat,
sinov, fix_kpi, qolda_baholar, bonus, tatil(keyin), config, bot_sessiya`.
`davomat.video_file_id` — dumaloq video isboti. Funksiya `imed_sof_min`. View: `v_davomat_kun, v_oylik_soat`.
> AmoCRM jadvallari (`amocrm_calls/tasks`) hozircha ishlatilmaydi — keyin.

---

## 7. FAZALAR (ixcham — 2 fazada ishga tushirish)

### FAZA 1 — Asosiy davomat (MVP)
- [ ] Supabase loyiha + schema (MCP orqali)
- [ ] grammY skelet: webhook, **private-only guard**, rol aniqlash, rol menyu, session
- [ ] Davomat: keldi/tushlik/ketdi + lokatsiya + **dumaloq video**
- [ ] Xodim boshqaruvi (qo'shish/tahrir/rol/arxiv)
- [ ] Kunlik hisobot → eski guruh + Davomat bo'limi (3393)
- [ ] avtoDavomat (3 kishi, 09:05)
- **Done:** davomat to'liq ishlaydi, eski bilan parallel test

### FAZA 2 — Maosh + hisobotlar (→ ishga tushirish)
- [ ] Sinov moduli
- [ ] KPI **qo'lда** kiritish + qo'lда baholar (CRM%, sifat)
- [ ] To'liq maosh (6 KPI + ovqat + bonus) — SQL view
- [ ] Dashboard + oylik hisobot + eksport (PDF/Excel maosh varaqasi)
- [ ] Davr tanlash (Bugun/Hafta/Oy/Yil/Maxsus)
- [ ] Cron (**node-cron**, bot ichida): 09:00/09:05/09:30/18:00/18:30 + oylik
- **Done:** oylik maosh avtomatik → **ISHGA TUSHIRISH** (webhook almashtirish, tunda)

### KEYIN (kechiktirilgan)
AmoCRM/UTel sync (avtomatik KPI), sotuv bonusi (tushum %), ta'til, moliya ko'prigi, face-ID.

---

## 8. KODLASH KONVENSIYALARI
- TypeScript strict, `any` dan qoch.
- Har handler kichik, sof funksiyalar; biznes-mantiq `services/`да.
- Xatolarни ushla, logla; foydalanuvchiga tushunarli xabar.
- Uzbek lotin (o'/g'/'), foydalanuvchi xabarlari uchun.
- Har feature'дан keyin: qisqa test + git commit.
- Vaqt zonasi: **Asia/Tashkent** (barcha sana/soat).

## 9. DEADLINE
Maqsad: **~15-avgust** (yangi oy o'rtasi) — FAZA 1+2 tayyor, parallel test o'tgan.
AmoCRM va boshqa kengaytmalar ishga tushirishдан keyin qo'shiladi.
