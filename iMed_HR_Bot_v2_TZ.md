# iMed HR Bot v2 — TEXNIK TOPSHIRIQ (TZ) va ROAD MAP
**Versiya:** 1.0 · **Sana:** 2026-07-10 · **Loyiha egasi:** Saidaxror Ismatullayev (iMed Team)
**Holat:** Rejalashtirish · **Bu hujjat:** yagona haqiqat manbai (single source of truth)
> Ushbu TZ oldingi barcha suhbatlardagi qarorlarni jamlaydi. Qurish shu hujjat asosida
> boradi. Yangi qaror qabul qilinsa — shu hujjat yangilanadi.
---
## 1. LOYIHA UMUMIY KO'RINISHI
### 1.1 Maqsad
iMed Team uchun to'liq, tez va avtomatik **HR + davomat + maosh** tizimini qurish.
Eski tizim (Google Apps Script + Sheets) sekin (2–5 soniya, kunlik kvota, 6 daqiqa limiti).
Yangi tizim Supabase (Postgres) + grammY bilan **0.1–0.3 soniyada** javob beradi, limitsiz.
### 1.2 Doira (scope) — KIRADI
Davomat, ish vaqti hisobi, xodim boshqaruvi, sinov, KPI, to'liq maosh (KPI + sotuv bonus),
avans/qarz, jarima/bonus, ta'til, ovqat puli, hisobotlar/Dashboard, davr tanlash,
hisobot eksporti (maosh varaqasi), AmoCRM/UTel sync, moliya ko'prigi, avtomatik cron.
### 1.3 Doiradan TASHQARI (bu loyihada emas)
Moliya botni qayta yozish (u alohida qoladi, faqat ko'prik), veb-dashboard (keyin),
turniket/qurilma (kelishilgan — shart emas), AI savol-javob (eng oxirgi bosqich).
### 1.4 Asosiy tamoyillar
1. **Uzilishsizlik** — eski bot to'liq test tugagunча ishlaydi, almashtirish tunda.
2. **NO HARD DELETE** — hech narsa o'chirilmaydi (`arxiv=true`).
3. **Deterministik hisob** — maosh/soat SQL bilan, AI'ga ishonilmaydi.
4. **Rol asosida menyu** — har kim faqat o'z tugmalarini ko'radi.
5. **Modulli, toza kod** — kengaytirish oson.
---
## 2. HOZIRGI HOLAT (as-is)
- **@imeddavomat_bot** — Apps Script + Sheets + AmoCRM. Davomat, maosh (qisman), KPI,
  ovqat puli, sinov, Dashboard, 7 trigger. **Sekin, limitli.**
- **@moliyaasistentimedbot / MARKAZIY BOT** — DigitalOcean + Supabase. Moliya
  (sotuv/tushum/qarz/xarajat, cash-basis, moliyachi tasdig'i).
- Maosh modeli **aniqlangan** (quyida), lekin to'liq avtomatik hisoblanmaydi.
---
## 3. FOYDALANUVCHILAR VA ROLLAR
| Rol | Kim | Nima ko'radi/qiladi |
|-----|-----|---------------------|
| **Sotuvchi** | 6 kishi | Davomat tugmalari (keldi/tushlik/ketdi) |
| **Nazoratchi/Rahbar** | ~4 | Davomat + barcha hisobot, xodim boshqaruvi, KPI kiritish, tasdiqlash |
| **Marketolog** | 2 | Davomat (ovqat puli oladi) |
| **Director (CEO)** | 1 | Davomat + to'liq ko'rinish |
| **Sinovchi** | o'zgaruvchan | Davomat (keldi/ketdi), sinov summasi |
---
## 4. FUNKSIONAL TALABLAR (FR)
### 4.1 Davomat moduli
- **FR-1.1** Keldi/Tushlikka/Ketdi tugmalari (rol bo'yicha).
- **FR-1.2** Lokatsiya tekshiruvi (ofis 40.385907, 71.786778, radius 100 m).
- **FR-1.3** Forward/eski lokatsiya rad (90 soniyadan eski → rad).
- **FR-1.4** Kech kelsa izoh so'rash (yoki o'tkazish).
- **FR-1.5** Tushlik faqat 12:00–14:00; avtomatik 1 soat + qaytish vaqti.
- **FR-1.6** Bir kun = bir qator; takror bosish bloklanadi.
### 4.2 Ish vaqti hisobi
- **FR-2.1** Qoida: oyna 09:00–18:00; erta kelish qo'shilmaydi; kech kelsa haqiqiy vaqt;
  ketmasa/kech ketsa 18:00; erta ketsa haqiqiy; tushlik ayiriladi. (`imed_sof_min` SQL)
- **FR-2.2** Kunlik norma 8 soat; oylik norma 176 soat.
### 4.3 Xodim boshqaruvi
- **FR-3.1** Qo'shish (ism, TG ID, rol, ish vaqti, AmoCRM avtomatik bog'lash).
- **FR-3.2** Ro'yxat (guruhlangan), tahrirlash, lavozim o'zgartirish.
- **FR-3.3** Ishdan chiqarish = arxiv (tarix saqlanadi).
### 4.4 Sinov
- **FR-4.1** Qo'shish: ism, TG ID, **umumiy fixed summa** (masalan 400 000 — butun davr).
- **FR-4.2** Bosqich: Adaptatsiya (1–3 kun) → Sinov+Imtihon (max 15 kun).
- **FR-4.3** Sinovchi davomat qiladi (keldi/ketdi).
- **FR-4.4** Imtihon natijasi: Qabul/Rad/Uzaytirish; muddat eslatmasi.
### 4.5 KPI (kunlik kiritish)
- **FR-5.1** Qo'ng'iroq soni, gaplashish daqiqasi — qo'lda yoki AmoCRM'dan.
- **FR-5.2** CRM tozaligi %, qo'ng'iroq sifati ball — qo'lda (oylik).
### 4.6 Maosh hisobi (to'liq) — biznes qoidasi 5-bo'limda
- **FR-6.1** Sotuvchi: 6 KPI (pool 4 mln) + sotuv bonusi (pog'onali).
- **FR-6.2** Rahbar/Marketolog: 1 mln fix + ovqat puli + KPI bonus − jarima.
- **FR-6.3** Yakuniy = maosh − avans − jarima + bonus + ovqat.
- **FR-6.4** Davr bo'yicha (tanlangan oy).
### 4.7 Avans / Qarz
- **FR-7.1** Rahbar avans beradi (kim, qancha, qaysi oy).
- **FR-7.2** Maoshdan avtomatik ushlanadi; qoldiq kuzatiladi.
### 4.8 Jarima / Bonus
- **FR-8.1** Qo'lda jarima/bonus (summa, sabab, oy).
- **FR-8.2** Hisobot intizomi jarimasi: sababsiz berilmagan har hisobot → kunlik fiksdan −10%.
- **FR-8.3** Kechikish jarimasi (ixtiyoriy, avtomatik — **[TASDIQLANSIN]**).
### 4.9 Ta'til / Dam olish
- **FR-9.1** Xodim ta'til so'raydi (tur, sana–sana, izoh).
- **FR-9.2** Rahbar tasdiqlaydi/rad etadi.
- **FR-9.3** Maoshga ta'sir — `tolanadi` bayrog'i (qoida **[keyin belgilanadi]**).
- **FR-9.4** Kim qachon ta'tilda — ko'rinish.
### 4.10 Hisobotlar & Dashboard
- **FR-10.1** Davr tanlash: Bugun/Hafta/Oy/Yil/Maxsus oraliq.
- **FR-10.2** Kunlik hisobot (avtomatik 18:30).
- **FR-10.3** Rahbar Dashboard: 6 KPI + sotuv bonus + ovqat + jarima/avans + to'lov ro'yxati.
- **FR-10.4** Bo'lim bo'yicha kesim (Sotuv/Marketing/Boshqaruv).
- **FR-10.5** Kunlik statistika (har xodim alohida), oy arxivi.
### 4.11 Eksport
- **FR-11.1** Har xodimga oylik maosh varaqasi (PDF/Excel) — barcha komponent bilan.
- **FR-11.2** Rahbarga umumiy to'lov jadvali (imzo joyi).
### 4.12 Avtomatik eslatmalar (cron)
- **FR-12.1** 09:00 "keldingizmi?", 09:30 kelmaganlar, 18:00 "ketdingizmi?".
- **FR-12.2** 18:30 kunlik hisobot, har kun sinov muddati, 1-sanada oylik + arxiv.
### 4.13 Integratsiya
- **FR-13.1** AmoCRM/UTel inkremental sync → Supabase.
- **FR-13.2** Moliya ko'prigi: oylik maosh → moliya botga xarajat sifatida.
---
## 5. BIZNES QOIDALARI (maosh modeli — aniqlangan)
### 5.1 SOTUVCHI maoshi
**Maosh = KPI pool (4 000 000) + Sotuv bonusi**
KPI pool (6 ko'rsatkich, har biri norma bo'yicha ulush × summa):
| # | Ko'rsatkich | Norma | Summa |
|---|-------------|-------|-------|
| 1 | Ish vaqti | 176 soat | 1 500 000 |
| 2 | Chiquvchi qo'ng'iroq | 2200/oy | 600 000 |
| 3 | Gaplashish | 3960 min/oy | 600 000 |
| 4 | Qayta aloqa (o'z vaqtida) | 90% | 300 000 |
| 5 | CRM tozaligi | 95% | 500 000 |
| 6 | Qo'ng'iroq sifati | 85/100 | 500 000 |
|   | **JAMI (pool)** |  | **4 000 000** |
Sotuv bonusi (tushum bo'yicha, pog'onali):
| Tushum | Bonus |
|--------|-------|
| 70 mln+ | 3% |
| 100 mln+ | 5% |
| 120 mln+ | 5% + 150 000 |
| 150 mln+ | 5% + 300 000 |
| 200 mln+ | 5% + 600 000 |
> Maksimal umumiy ≈ **14 600 000**. (Sotuv bonusi 2-bosqich — arxitektura tayyor bo'lsin.)
### 5.2 RAHBAR (CEO, Moliyachi, Marketolog, Editor) maoshi
**Maosh = 1 000 000 FIX − jarima(−10%/hisobot) + ovqat(40 000 × ish kuni) + KPI bonus**
> Rahbar KPI bonus summalari **aniqlanmagan** — **[OCHIQ]**.
### 5.3 Jarima (hisobot intizomi)
- Har xodimga kunlik hisobotlar belgilangan.
- Sababsiz berilmagan **har bir** hisobot → kunlik fiksdan **−10%**.
- Tizim avtomatik kuzatadi (kim, qaysi, qachon).
### 5.4 Ovqat puli
- Rahbar + Marketolog: kelgan kun × 40 000.
### 5.5 Sinov
- Butun sinov davri uchun **fixed umumiy summa** (masalan 400 000, bir marta).
### 5.6 Yakuniy to'lov
`Yakuniy = maosh + ovqat + bonus − avans − jarima` (ta'til ta'siri qoidasi keyin).
---
## 6. NOFUNKSIONAL TALABLAR (NFR)
- **NFR-1 Tezlik:** javob < 0.5 soniya (odatda 0.1–0.3).
- **NFR-2 Miqyos:** xodim/hisobot ko'paysa sekinlashmaydi (indeks + SQL).
- **NFR-3 Ishonchlilik:** takror xabar himoyasi (update_id), atomar yozuv.
- **NFR-4 Auditlik:** har o'zgarish tarixi (created_at/updated_at, arxiv).
- **NFR-5 Xavfsizlik:** service_role kalit faqat serverda; token env'da; RLS eslatma.
- **NFR-6 Kuzatuv:** loglar, xatolik xabari (@imedfinancebot orqali ogohlantirish mumkin).
---
## 7. ARXITEKTURA
```
Telegram  ──webhook──►  grammY bot (DigitalOcean, Node.js/TS)
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
                Supabase   AmoCRM    node-cron
                (Postgres)  /UTel   (eslatma+hisobot)
                    │
                    └──ko'prik──►  Moliya bot (Supabase) [maosh=xarajat]
```
- **Til/framework:** TypeScript + grammY
- **Baza:** Supabase (Postgres) — yagona haqiqat manbai
- **Server:** DigitalOcean (bor)
- **Cron:** node-cron (yoki Supabase pg_cron)
- **Eksport:** PDF/Excel generatsiya (server tomonda)
---
## 8. MA'LUMOTLAR MODELI
To'liq sxema: **`iMed_HR_Bot_v2_schema.sql`** (alohida fayl).
Asosiy jadvallar: `xodimlar, davomat, sinov, fix_kpi, qolda_baholar, avans,
jarima_bonus, tatil, amocrm_calls, amocrm_tasks, config, bot_sessiya`.
Markaziy funksiya: `imed_sof_min()`. Ko'rinishlar: `v_davomat_kun, v_oylik_soat`.
> Sxema kengaytiriladi: maosh hisobi uchun `v_maosh_oylik` view + sotuv bonus jadvali
> (AmoCRM won bitimlaridan) 4/5-bosqichda qo'shiladi.
---
## 9. INTEGRATSIYALAR
### 9.1 AmoCRM / UTel (aniqroq sync)
- Inkremental (`updated_at > kursor`), dublikatsiz (`id` primary key).
- Attributsiya: `responsible_user_id` (created_by emas).
- Javob berilgan (duration>0) vs berilmagan ajratiladi.
- Vaqt zonasi Asia/Tashkent.
- **[TASDIQLANSIN]** manba: AmoCRM notes yoki UTel API (aniqroq).
### 9.2 Moliya ko'prigi
- 2 bot alohida; faqat ma'lumot o'tadi.
- Oylik maosh yakunlanганда → moliya botga **xarajat** sifatida yoziladi.
- **[TASDIQLANSIN]** interfeys: umumiy Supabase, yoki HTTP endpoint, yoki jadval.
---
## 10. TEST REJASI
- Test bot tokeni bilan alohida muhit.
- Har modul yozilgach — real ma'lumotда tekshiriladi.
- Eski bot bilan **parallel solishtirish** (bir hafta bir xil davomat).
- Chegaraviy holatlar: ketmagan kun, kech kelish, tushliksiz kun, oy chegarasi, ta'til.
## 11. MIGRATSIYA (uzilishsiz)
1. Google Sheets → CSV → Supabase (bir martalik import + tekshiruv).
2. Yangi bot test bot bilan to'liq test.
3. Tunda webhook almashtirish (eski token → yangi server).
4. Eski Apps Script bot **zaxira** (muammo bo'lsa qaytariladi).
## 12. RISKLAR
| Risk | Ta'sir | Yechim |
|------|--------|--------|
| AmoCRM rate-limit | Sync sekin | Inkremental + backoff |
| Ma'lumot import xatosi | Noto'g'ri maosh | CSV tekshiruv, parallel solishtirish |
| Almashtirishда uzilish | Xodim davomat qilolmaydi | Tunda + eski bot zaxira |
| Ochiq qoidalar (ta'til, rahbar bonus) | Kechikish | Bayroq/placeholder bilan tayyor |
---
## 13. ROAD MAP (fazalar)
### FAZA 0 — Poydevor ✅ (boshlandi)
- [x] TZ + Road map (shu hujjat)
- [x] Supabase sxema (`schema.sql`)
- [ ] Sxemani yangi Supabase loyihasiga qo'llash
- [ ] Google Sheets → Supabase import
### FAZA 1 — Asosiy bot (MVP)
- [ ] grammY skelet: webhook + rol aniqlash + rol menyu + sessiya
- [ ] Davomat oqimi (keldi/tushlik/ketdi + lokatsiya)
- [ ] Xodim boshqaruvi (qo'shish/tahrir/rol/arxiv)
- [ ] Kunlik hisobot (SQL) + guruhga (Davomat mavzusi) yuborish
- **Milestone:** davomat to'liq ishlaydi, eski bilan parallel test
### FAZA 2 — Maosh & KPI
- [ ] Sinov moduli
- [ ] KPI kiritish + qo'lda baholar
- [ ] To'liq maosh hisobi (6 KPI + ovqat) — SQL view
- [ ] Rahbar Dashboard + oylik hisobot + eksport (PDF/Excel)
- **Milestone:** oylik maosh avtomatik, aniq
### FAZA 3 — HR modullar
- [ ] Davr tanlash (Bugun/Hafta/Oy/Yil/Maxsus)
- [ ] Avans/Qarz
- [ ] Jarima/Bonus (+ hisobot intizomi −10%)
- [ ] Ta'til/Dam olish (so'rov → tasdiq → maoshga ta'sir)
- **Milestone:** to'liq HR tizim
### FAZA 4 — Integratsiya & avtomatika
- [ ] AmoCRM/UTel inkremental sync
- [ ] Sotuv bonusi (tushum %, AmoCRM won)
- [ ] Moliya ko'prigi (maosh → xarajat)
- [ ] Cron (eslatma + avtomatik hisobot)
- **Milestone:** to'liq avtomatik, mustaqil
### FAZA 5 — Ishga tushirish
- [ ] To'liq test (parallel bir hafta)
- [ ] Ma'lumot yakuniy ko'chirish
- [ ] Webhook almashtirish (tunda)
- [ ] Kuzatuv + eski bot zaxira
- **Milestone:** production, eski bot o'chiriladi
### KELAJAK (bu TZ'dan tashqari)
- Face-ID / round video (anti-forward)
- Veb-dashboard
- AI savol-javob (ovozli/matn)
---
## 14. OCHIQ QARORLAR (jurnal)
| # | Savol | Holat |
|---|-------|-------|
| 1 | Server | ✅ DigitalOcean |
| 2 | AmoCRM manba (notes/UTel) | ⏳ ochiq |
| 3 | Ta'til maoshga ta'siri | ⏳ keyin |
| 4 | Kechikish jarimasi (avtomatik summa) | ⏳ ochiq |
| 5 | Rahbar KPI bonus summalari | ⏳ ochiq |
| 6 | Moliya ko'prik interfeysi | ⏳ ochiq |
| 7 | Sotuv bonusi qachon yoqiladi | ⏳ 2-bosqich |
---
*Keyingi qadam: FAZA 0 ni tugatish — sxemani Supabase'ga qo'llash, keyin FAZA 1 grammY skelet.*
