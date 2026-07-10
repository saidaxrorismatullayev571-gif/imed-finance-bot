-- ============================================================
--  iMed HR Bot v2 — SUPABASE (Postgres) SXEMASI
--  1-QADAM: Poydevor. Yangi Supabase loyihasida ishga tushiring.
--  (Eski Google Sheets tizimiga TEGILMAYDI.)
--
--  Tamoyillar:
--   • NO HARD DELETE — hech narsa o'chirilmaydi (arxiv=true).
--   • Deterministik hisob — sof ish vaqti SQL funksiyasida.
--   • Vaqt zonasi: Asia/Tashkent.
-- ============================================================

-- ---------- 0. Yordamchi: updated_at avtomatik yangilash ----------
create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at := now();
  return new;
end $$;

-- ============================================================
--  1. XODIMLAR
-- ============================================================
create table if not exists xodimlar (
  id             bigint generated always as identity primary key,
  telegram_id    bigint unique not null,
  ism            text not null,
  bolim          text,                         -- Sotuv / Boshqaruv / Marketing
  rol            text not null default 'Sotuvchi'
                 check (rol in ('Sotuvchi','Nazoratchi','Marketolog','Director','Test')),
  ish_boshi      time not null default '09:00',
  ish_tugash     time not null default '18:00',
  amocrm_id      bigint,                        -- AmoCRM user id (nullable)
  telefon        text,
  arxiv          boolean not null default false, -- ishdan chiqsa true (o'chirilmaydi)
  arxiv_sana     date,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);
create index if not exists idx_xodim_tgid   on xodimlar(telegram_id);
create index if not exists idx_xodim_amocrm on xodimlar(amocrm_id);
create index if not exists idx_xodim_rol    on xodimlar(rol) where arxiv = false;
drop trigger if exists trg_xodim_upd on xodimlar;
create trigger trg_xodim_upd before update on xodimlar
  for each row execute function set_updated_at();

-- ============================================================
--  2. SOF ISH VAQTI FUNKSIYASI (markaziy qoida)
--    • Ish oynasi 09:00–18:00
--    • 09:00 dan erta kelsa → 09:00 dan (ortiqcha hisoblanmaydi)
--    • 09:00 dan kech kelsa → haqiqiy kech vaqtdan
--    • Ketmasa/kech ketsa → 18:00 gacha; erta ketsa → haqiqiy vaqt
--    • Tushlik (1 soat, yoki qaytdi−tushlikka) ayiriladi
-- ============================================================
create or replace function imed_sof_min(
  p_keldi     timestamptz,
  p_tushlikka timestamptz,
  p_qaytdi    timestamptz,
  p_ketdi     timestamptz
) returns int language plpgsql stable as $$
declare
  tz       text := 'Asia/Tashkent';
  ish_bosh int  := 9*60;    -- 09:00
  ish_tuga int  := 18*60;   -- 18:00
  k int; ke int; t int; q int;
  s int; e int; lunch int := 0;
begin
  if p_keldi is null then return 0; end if;

  k := extract(hour   from (p_keldi at time zone tz))::int * 60
     + extract(minute from (p_keldi at time zone tz))::int;

  if p_ketdi is not null then
    ke := extract(hour   from (p_ketdi at time zone tz))::int * 60
        + extract(minute from (p_ketdi at time zone tz))::int;
  else ke := null; end if;

  if p_tushlikka is not null then
    t := extract(hour   from (p_tushlikka at time zone tz))::int * 60
       + extract(minute from (p_tushlikka at time zone tz))::int;
  else t := null; end if;

  if p_qaytdi is not null then
    q := extract(hour   from (p_qaytdi at time zone tz))::int * 60
       + extract(minute from (p_qaytdi at time zone tz))::int;
  else q := null; end if;

  s := greatest(k, ish_bosh);
  if ke is null then e := ish_tuga; else e := least(ke, ish_tuga); end if;
  if e <= s then return 0; end if;

  if t is not null and q is not null and q > t then
    lunch := q - t;
    if lunch > 90 then lunch := 60; end if;
  elsif t is not null then
    lunch := 60;
  end if;

  return greatest(0, e - s - lunch);
end $$;

-- ============================================================
--  3. DAVOMAT (kunlik qatnashuv)
-- ============================================================
create table if not exists davomat (
  id           bigint generated always as identity primary key,
  telegram_id  bigint not null references xodimlar(telegram_id),
  sana         date not null,
  keldi        timestamptz,
  tushlikka    timestamptz,
  qaytdi       timestamptz,
  ketdi        timestamptz,
  sof_min      int not null default 0,          -- avtomatik (trigger orqali)
  erta_min     int not null default 0,          -- info: 09:00 gacha necha daqiqa erta
  holat        text,                            -- Vaqtida / Erta keldi / Kech qoldi / Ruxsatli kech / Kelmadi
  izoh         text,
  lat          double precision,
  lng          double precision,
  masofa_m     int,
  video_file_id text,                            -- dumaloq video (video note) file_id — isbot
  is_sinov     boolean not null default false,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  unique (telegram_id, sana)                     -- bir kun = bir qator
);
create index if not exists idx_davomat_sana on davomat(sana);
create index if not exists idx_davomat_tg_sana on davomat(telegram_id, sana);

-- sof_min ni avtomatik hisoblab qo'yish
create or replace function davomat_hisobla()
returns trigger language plpgsql as $$
begin
  new.sof_min := imed_sof_min(new.keldi, new.tushlikka, new.qaytdi, new.ketdi);
  return new;
end $$;
drop trigger if exists trg_davomat_calc on davomat;
create trigger trg_davomat_calc before insert or update on davomat
  for each row execute function davomat_hisobla();

drop trigger if exists trg_davomat_upd on davomat;
create trigger trg_davomat_upd before update on davomat
  for each row execute function set_updated_at();

-- ============================================================
--  4. SINOV (trial)
-- ============================================================
create table if not exists sinov (
  id            bigint generated always as identity primary key,
  telegram_id   bigint not null,
  ism           text not null,
  bolim         text,
  boshlanish    date not null,
  tugash_max    date not null,
  summa_umumiy  bigint not null,                -- FIXED umumiy summa (butun davr uchun)
  bosqich       text not null default 'Adaptatsiya'
                check (bosqich in ('Adaptatsiya','Sinov+Imtihon')),
  natija        text check (natija in ('Qabul','Rad','Kutilmoqda') or natija is null),
  kelgan_kun    int not null default 0,
  imtihon_sana  date,
  izoh          text,
  arxiv         boolean not null default false,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
create index if not exists idx_sinov_tgid on sinov(telegram_id) where arxiv = false;
drop trigger if exists trg_sinov_upd on sinov;
create trigger trg_sinov_upd before update on sinov
  for each row execute function set_updated_at();

-- ============================================================
--  5. FIX KPI (kunlik: qo'ng'iroq / gaplashish)
-- ============================================================
create table if not exists fix_kpi (
  id           bigint generated always as identity primary key,
  telegram_id  bigint not null,
  sana         date not null,
  qongiroq     int not null default 0,
  gaplashish   int not null default 0,           -- daqiqa
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  unique (telegram_id, sana)
);
drop trigger if exists trg_fixkpi_upd on fix_kpi;
create trigger trg_fixkpi_upd before update on fix_kpi
  for each row execute function set_updated_at();

-- ============================================================
--  6. QO'LDA BAHOLAR (CRM tozaligi %, Sifat ball) — oylik
-- ============================================================
create table if not exists qolda_baholar (
  id           bigint generated always as identity primary key,
  telegram_id  bigint not null,
  oy           text not null,                    -- 'YYYY-MM'
  crm_foiz     numeric(5,2) default 0,           -- norma 95
  sifat_ball   numeric(5,2) default 0,           -- norma 85 (100 dan)
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  unique (telegram_id, oy)
);
drop trigger if exists trg_qolda_upd on qolda_baholar;
create trigger trg_qolda_upd before update on qolda_baholar
  for each row execute function set_updated_at();

-- ============================================================
--  7. BONUS  (jarima olib tashlandi — faqat bonus)
-- ============================================================
create table if not exists bonus (
  id           bigint generated always as identity primary key,
  telegram_id  bigint not null,
  summa        bigint not null,                  -- musbat qiymat
  sana         date not null default current_date,
  oy           text not null,                    -- 'YYYY-MM'
  sabab        text,
  created_at   timestamptz not null default now()
);
create index if not exists idx_bonus_tg_oy on bonus(telegram_id, oy);

-- ============================================================
--  8. TA'TIL / DAM OLISH  (keyinchalik foydalaniladi)
-- ============================================================
create table if not exists tatil (
  id           bigint generated always as identity primary key,
  telegram_id  bigint not null,
  tur          text not null default 'yillik'
               check (tur in ('yillik','kasallik','sababli','sababsiz')),
  boshlanish   date not null,
  tugash       date not null,
  kun_soni     int generated always as ((tugash - boshlanish) + 1) stored,
  holat        text not null default 'kutilmoqda'
               check (holat in ('kutilmoqda','tasdiqlandi','rad')),
  tolanadi     boolean not null default true,    -- maoshga ta'sir (keyin belgilanadi)
  sorov_izoh   text,
  tasdiq_by    bigint,                           -- qaysi rahbar tasdiqladi
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
create index if not exists idx_tatil_tg on tatil(telegram_id);
create index if not exists idx_tatil_holat on tatil(holat);
drop trigger if exists trg_tatil_upd on tatil;
create trigger trg_tatil_upd before update on tatil
  for each row execute function set_updated_at();

-- ============================================================
--  10. AMOCRM SYNC (inkremental) — hisobotlar SQL'dan chiqsin
-- ============================================================
create table if not exists amocrm_calls (
  id            bigint primary key,              -- AmoCRM note id (dublikat oldini oladi)
  amocrm_user   bigint not null,                 -- responsible_user_id
  yonalish      text,                            -- in / out
  davomiylik    int not null default 0,          -- sekund (0 = javob berilmagan)
  vaqt          timestamptz not null,
  created_at    timestamptz not null default now()
);
create index if not exists idx_calls_user_vaqt on amocrm_calls(amocrm_user, vaqt);

create table if not exists amocrm_tasks (
  id            bigint primary key,              -- AmoCRM task id
  amocrm_user   bigint not null,
  bajarildi     boolean not null default false,
  oz_vaqtida    boolean not null default false,  -- completed_at <= complete_till
  vaqt          timestamptz not null,
  created_at    timestamptz not null default now()
);
create index if not exists idx_tasks_user_vaqt on amocrm_tasks(amocrm_user, vaqt);

-- ============================================================
--  11. KONFIG / SESSIYA
-- ============================================================
create table if not exists config (
  kalit  text primary key,
  qiymat text
);
-- sync kursorlari va sozlamalar shu yerda saqlanadi
insert into config(kalit, qiymat) values
  ('amocrm_last_call_sync','0'),
  ('amocrm_last_task_sync','0')
on conflict (kalit) do nothing;

create table if not exists bot_sessiya (
  telegram_id  bigint primary key,
  step         text,
  data         jsonb default '{}'::jsonb,
  updated_at   timestamptz not null default now()
);
drop trigger if exists trg_sessiya_upd on bot_sessiya;
create trigger trg_sessiya_upd before update on bot_sessiya
  for each row execute function set_updated_at();

-- ============================================================
--  12. KO'RINISHLAR (VIEW) — tez hisobotlar
-- ============================================================

-- Kunlik davomat + ism/rol
create or replace view v_davomat_kun as
select d.sana, d.telegram_id, x.ism, x.rol, x.bolim,
       d.keldi, d.tushlikka, d.qaytdi, d.ketdi,
       d.sof_min, d.holat, d.izoh
from davomat d
join xodimlar x on x.telegram_id = d.telegram_id
where x.arxiv = false;

-- Oylik jami ish soati (har xodim)
create or replace view v_oylik_soat as
select x.telegram_id, x.ism, x.rol, x.bolim,
       to_char(d.sana,'YYYY-MM') as oy,
       count(*) filter (where d.keldi is not null) as kelgan_kun,
       coalesce(sum(d.sof_min),0)                  as jami_min,
       round(coalesce(sum(d.sof_min),0)/60.0, 1)   as jami_soat
from xodimlar x
left join davomat d on d.telegram_id = x.telegram_id
where x.arxiv = false
group by x.telegram_id, x.ism, x.rol, x.bolim, to_char(d.sana,'YYYY-MM');

-- ============================================================
--  RLS eslatma:
--   Bot backend service_role kaliti bilan ulanadi (RLS'ni chetlab o'tadi).
--   Shu sabab RLS yoqilmagan. Agar public anon kalit ishlatilsa —
--   har jadvalga RLS + policy qo'shish shart.
-- ============================================================

-- Tayyor. Keyingi qadam: grammY skelet (rol + menyu + sessiya).
