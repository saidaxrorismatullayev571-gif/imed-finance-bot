#!/usr/bin/env bash
set -euo pipefail

echo "== iMed HR Bot -- Contabo serverga o'rnatish boshlandi =="

# 1) Deno o'rnatish (unzip kerak bo'ladi)
if ! command -v unzip &>/dev/null; then
  sudo apt-get update -y
  sudo apt-get install -y unzip
fi
if ! command -v deno &>/dev/null && [ ! -x "$HOME/.deno/bin/deno" ]; then
  curl -fsSL https://deno.land/install.sh | sh
fi
export DENO_INSTALL="$HOME/.deno"
export PATH="$DENO_INSTALL/bin:$PATH"
DENO_BIN="$(command -v deno || echo "$HOME/.deno/bin/deno")"
echo "Deno: $DENO_BIN ($($DENO_BIN --version | head -1))"

# 2) Caddy o'rnatish (avtomatik HTTPS uchun)
if ! command -v caddy &>/dev/null; then
  sudo apt-get update -y
  sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl gnupg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
  sudo apt-get update -y
  sudo apt-get install -y caddy
fi
echo "Caddy: $(caddy version)"

# 3) Loyiha papkasi
sudo mkdir -p /opt/imed-hr-bot
sudo chown "$USER":"$USER" /opt/imed-hr-bot
cd /opt/imed-hr-bot

echo "-- Fayllar yozilmoqda --"
cat > index.ts <<'IMEDHRBOT_INDEX_EOF'
import { Bot, InlineKeyboard, Keyboard, InputFile, webhookCallback } from "npm:grammy@1.21.1";
import { createClient } from "npm:@supabase/supabase-js@2.45.0";
import { davomatPng, davomatOraliqPng, type DavomatRow, type DavomatOraliqRow } from "./render.ts";
import { maoshXlsx, davomatXlsx, davomatOraliqXlsx, type MaoshXRow, type DavomatXRow, type DavomatOraliqXRow } from "./excel.ts";
import { pngToPdf, maoshPdf } from "./pdf.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const sb = createClient(SUPABASE_URL, SERVICE_KEY);

const OFIS_LAT = 40.385907;
const OFIS_LNG = 71.786778;
const TZ = "Asia/Tashkent";

// ── Yordamchi: config ─────────────────────────────────────────────
async function getConfig(kalit: string): Promise<string | null> {
  const { data } = await sb.from("config").select("qiymat").eq("kalit", kalit).maybeSingle();
  return data?.qiymat ?? null;
}
async function setConfig(kalit: string, qiymat: string) {
  await sb.from("config").upsert({ kalit, qiymat });
}

// ── Yordamchi: masofa (haversine, metr) ───────────────────────────
function distanceM(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const R = 6371000, toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1), dLng = toRad(lng2 - lng1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function escHtml(s: unknown): string {
  return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function tashkentParts(d: Date) {
  const f = new Intl.DateTimeFormat("en-CA", {
    timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  });
  const parts: Record<string, string> = {};
  for (const p of f.formatToParts(d)) parts[p.type] = p.value;
  return parts;
}
function todayTashkent(): string {
  const p = tashkentParts(new Date());
  return `${p.year}-${p.month}-${p.day}`;
}
function timeHms(d: Date): string {
  const p = tashkentParts(d);
  return `${p.hour}:${p.minute}:${p.second}`;
}
function minutesOfDay(d: Date): number {
  const p = tashkentParts(d);
  return parseInt(p.hour) * 60 + parseInt(p.minute);
}

// ── Sessiya (bot_sessiya jadvali) ─────────────────────────────────
interface Sess { step: string | null; data: Record<string, unknown>; }
async function getSess(tgId: number): Promise<Sess> {
  const { data } = await sb.from("bot_sessiya").select("step,data").eq("telegram_id", tgId).maybeSingle();
  return { step: data?.step ?? null, data: (data?.data as Record<string, unknown>) ?? {} };
}
async function setSess(tgId: number, step: string | null, data: Record<string, unknown> = {}) {
  await sb.from("bot_sessiya").upsert({ telegram_id: tgId, step, data, updated_at: new Date().toISOString() });
}
async function clearSess(tgId: number) {
  await setSess(tgId, null, {});
}

// ── Xodim / rol huquqlari ──────────────────────────────────────────
interface Xodim {
  id: number; telegram_id: number; ism: string; bolim: string | null;
  rol: string; arxiv: boolean; super_admin: boolean; hisobga_olinmaydi: boolean;
}
interface RolHuquq {
  nom: string; hisobot_koradi: boolean; xodim_boshqaradi: boolean; maosh_koradi: boolean;
  sinov_boshqaradi: boolean; signal_oladi: boolean; sozlama_boshqaradi: boolean; davomat_tuzata_oladi: boolean;
}
async function getXodim(tgId: number): Promise<Xodim | null> {
  const { data } = await sb.from("xodimlar").select("*").eq("telegram_id", tgId).eq("arxiv", false).maybeSingle();
  return data as Xodim | null;
}
async function getHuquq(rol: string): Promise<RolHuquq | null> {
  const { data } = await sb.from("rollar").select("*").eq("nom", rol).maybeSingle();
  return data as RolHuquq | null;
}
async function isBoshqaruvchi(x: Xodim): Promise<boolean> {
  if (x.super_admin) return true;
  const h = await getHuquq(x.rol);
  return !!(h?.xodim_boshqaradi);
}

const BTN_KELDIM = "Keldim";
const BTN_TUSHLIKKA = "Tushlikka";
const BTN_KETDIM = "Ketdim";
const BTN_XODIMLAR = "Xodimlar";
const BTN_HISOBOT = "Hisobot";
const BTN_SINOV = "Sinov";
const BTN_MAOSH = "Maosh";
const BTN_SOZLAMALAR = "Sozlamalar";
const BTN_BEKOR = "Bekor qilish";

async function mainMenu(x: Xodim): Promise<Keyboard> {
  const h = await getHuquq(x.rol);
  const kb = new Keyboard();
  // Direktor davomati avto_davomat() cron orqali avtomatik yoziladi (09:05,
  // har ish kuni) — shu sabab ularga qo'lda Keldim/Tushlikka/Ketdim tugmasi kerak emas.
  if (x.rol !== "Director") kb.text(BTN_KELDIM).text(BTN_TUSHLIKKA).text(BTN_KETDIM).row();
  const admin2 = x.super_admin || h?.xodim_boshqaradi;
  if (admin2) kb.text(BTN_XODIMLAR);
  if (x.super_admin || h?.hisobot_koradi) kb.text(BTN_HISOBOT);
  if (x.super_admin || h?.sinov_boshqaradi) kb.text(BTN_SINOV);
  kb.row();
  if (x.super_admin || h?.maosh_koradi) kb.text(BTN_MAOSH);
  if (x.super_admin || h?.sozlama_boshqaradi) kb.text(BTN_SOZLAMALAR);
  return kb.resized();
}

// ── Guruhga xabar yuborish ─────────────────────────────────────────
async function xulosaTarget(): Promise<{ chatId: string; topic?: number } | null> {
  const gid = await getConfig("xulosa_group_id");
  const topic = await getConfig("xulosa_topic_id");
  if (!gid) return null;
  return { chatId: gid, topic: topic ? parseInt(topic) : undefined };
}

function davomatXabarMatn(opts: {
  bolim: string; ism: string; holat: string; vaqt: string; sana: string; maps?: string;
}): string {
  let t = `<b>DAVOMAT</b>\n\n`;
  t += `<b>Bo'lim:</b> ${escHtml(opts.bolim || "-")}\n`;
  t += `<b>Xodim:</b> ${escHtml(opts.ism)}\n`;
  t += `<b>Holat:</b> ${escHtml(opts.holat)}\n`;
  t += `<b>Vaqt:</b> ${opts.vaqt}\n`;
  t += `<b>Sana:</b> ${opts.sana}`;
  if (opts.maps) t += `\n<b>Maps:</b> ${opts.maps}`;
  return t;
}

// ═══════════════════════════════════════════════════════════════════
// Bot tokeni DB'dan olinadi — bu tarmoq chaqiruvi modul yuklanishida (top-level await)
// EMAS, birinchi so'rovda amalga oshiriladi va keshlanadi. Shu bilan config query bir
// martalik uzilib qolsa ham funksiya butunlay "o'lik" holatda qolmaydi — keyingi so'rov
// qayta urinadi.
async function initBot(): Promise<Bot> {
  const { data: tokenRow } = await sb.from("config").select("qiymat").eq("kalit", "bot_token").maybeSingle();
  const token = tokenRow?.qiymat || Deno.env.get("BOT_TOKEN") || "";
  const bot = new Bot(token);

  bot.use(async (ctx, next) => {
  if (ctx.chat && ctx.chat.type !== "private") return; // faqat shaxsiy chat
  await next();
});

bot.command("start", async (ctx) => {
  const tgId = ctx.from!.id;
  await clearSess(tgId);
  const x = await getXodim(tgId);
  if (!x) {
    await ctx.reply(
      `Assalomu alaykum!\n\nSiz hozircha tizimda ro'yxatdan o'tmagansiz.\n` +
      `Administratorga shu Telegram ID raqamingizni bering: <code>${tgId}</code>`,
      { parse_mode: "HTML" },
    );
    return;
  }
  await ctx.reply(`Assalomu alaykum, ${x.ism}!`, { reply_markup: await mainMenu(x) });
});

bot.hears(BTN_BEKOR, async (ctx) => {
  await clearSess(ctx.from!.id);
  const x = await getXodim(ctx.from!.id);
  if (x) await ctx.reply("Bekor qilindi.", { reply_markup: await mainMenu(x) });
});

// ── DAVOMAT: Keldim ────────────────────────────────────────────────
bot.hears(BTN_KELDIM, async (ctx) => {
  const tgId = ctx.from!.id;
  const x = await getXodim(tgId);
  if (!x) return ctx.reply("Siz ro'yxatdan o'tmagansiz.");
  const sana = todayTashkent();
  const { data: davomat } = await sb.from("davomat").select("keldi").eq("telegram_id", tgId).eq("sana", sana).maybeSingle();
  if (davomat?.keldi) return ctx.reply("Siz allaqachon bugun ishga kelgansiz.");
  await setSess(tgId, "dm_loc_keldi", {});
  await ctx.reply("Lokatsiyangizni yuboring.", {
    reply_markup: new Keyboard().requestLocation("Lokatsiya yuborish").text(BTN_BEKOR).resized(),
  });
});

// ── DAVOMAT: Ketdim ────────────────────────────────────────────────
bot.hears(BTN_KETDIM, async (ctx) => {
  const tgId = ctx.from!.id;
  const x = await getXodim(tgId);
  if (!x) return ctx.reply("Siz ro'yxatdan o'tmagansiz.");
  const sana = todayTashkent();
  const { data: davomat } = await sb.from("davomat").select("keldi,ketdi").eq("telegram_id", tgId).eq("sana", sana).maybeSingle();
  if (!davomat?.keldi) return ctx.reply("Avval 'Keldim' tugmasini bosing.");
  if (davomat?.ketdi) return ctx.reply("Siz allaqachon bugun ishdan ketgansiz.");
  await setSess(tgId, "dm_loc_ketdi", {});
  await ctx.reply("Lokatsiyangizni yuboring.", {
    reply_markup: new Keyboard().requestLocation("Lokatsiya yuborish").text(BTN_BEKOR).resized(),
  });
});

// ── DAVOMAT: Tushlikka (lokatsiya/video shart emas, faqat vaqt oynasi) ─
bot.hears(BTN_TUSHLIKKA, async (ctx) => {
  const tgId = ctx.from!.id;
  const x = await getXodim(tgId);
  if (!x) return ctx.reply("Siz ro'yxatdan o'tmagansiz.");
  const sana = todayTashkent();
  const { data: davomat } = await sb.from("davomat").select("keldi,ketdi,tushlikka").eq("telegram_id", tgId).eq("sana", sana).maybeSingle();
  if (!davomat?.keldi) return ctx.reply("Avval 'Keldim' tugmasini bosing.");
  if (davomat?.ketdi) return ctx.reply("Siz bugun allaqachon ishdan ketgansiz, tushlikka chiqib bo'lmaydi.");
  if (davomat?.tushlikka) return ctx.reply("Siz allaqachon bugun tushlikka chiqqansiz.");
  const min = minutesOfDay(new Date());
  if (min < 12 * 60 || min > 14 * 60) {
    return ctx.reply("Tushlikka tugmasi faqat 12:00–14:00 oralig'ida ishlaydi.");
  }
  const now = new Date();
  await sb.from("davomat").update({ tushlikka: now.toISOString() }).eq("telegram_id", tgId).eq("sana", sana);
  await ctx.reply("Qabul qilindi — tushlik (1 soat) hisoblandi.");
  const target = await xulosaTarget();
  if (target) {
    const text = davomatXabarMatn({
      bolim: x.bolim ?? "", ism: x.ism, holat: "tushlikka chiqdi (1 soat)",
      vaqt: timeHms(now), sana: todayTashkent(),
    });
    await bot.api.sendMessage(target.chatId, text, { message_thread_id: target.topic, parse_mode: "HTML" }).catch(() => {});
  }
});

// ── Lokatsiya qabul qilish ─────────────────────────────────────────
bot.on("message:location", async (ctx) => {
  const tgId = ctx.from!.id;
  const sess = await getSess(tgId);
  if (sess.step !== "dm_loc_keldi" && sess.step !== "dm_loc_ketdi") return;

  const msgAge = Date.now() / 1000 - ctx.message!.date;
  // deno-lint-ignore no-explicit-any
  const fwd = (ctx.message as any).forward_origin || (ctx.message as any).forward_date;
  if (fwd || msgAge > 90) {
    await ctx.reply("Eski yoki forward qilingan lokatsiya qabul qilinmaydi. Qaytadan jonli lokatsiya yuboring.");
    return;
  }
  const loc = ctx.message!.location!;
  const radiusStr = await getConfig("ofis_radius_m");
  const radius = radiusStr ? parseInt(radiusStr) : 100;
  const dist = distanceM(loc.latitude, loc.longitude, OFIS_LAT, OFIS_LNG);
  if (dist > radius) {
    await ctx.reply(`Siz ofisdan uzoqdasiz (${Math.round(dist)} m). Ofis hududida bo'lishingiz kerak.`);
    return;
  }

  const nextStep = sess.step === "dm_loc_keldi" ? "dm_vid_keldi" : "dm_vid_ketdi";
  await setSess(tgId, nextStep, { lat: loc.latitude, lng: loc.longitude, masofa: Math.round(dist) });
  await ctx.reply("Endi dumaloq video (video xabar) yuboring.", {
    reply_markup: new Keyboard().text(BTN_BEKOR).resized(),
  });
});

// ── Dumaloq video qabul qilish ─────────────────────────────────────
bot.on("message:video_note", async (ctx) => {
  const tgId = ctx.from!.id;
  const sess = await getSess(tgId);
  if (sess.step !== "dm_vid_keldi" && sess.step !== "dm_vid_ketdi") return;

  const msgAge = Date.now() / 1000 - ctx.message!.date;
  // deno-lint-ignore no-explicit-any
  const fwd = (ctx.message as any).forward_origin || (ctx.message as any).forward_date;
  if (fwd || msgAge > 90) {
    await ctx.reply("Eski yoki forward qilingan video qabul qilinmaydi. Qaytadan o'zingiz video yuboring.");
    return;
  }

  const x = await getXodim(tgId);
  if (!x) return;
  const sana = todayTashkent();
  const now = new Date();
  const fileId = ctx.message!.video_note!.file_id;
  const lat = sess.data.lat as number, lng = sess.data.lng as number, masofa = sess.data.masofa as number;
  const isKeldi = sess.step === "dm_vid_keldi";

  const { data: sinovAktiv } = await sb.from("sinov").select("id").eq("telegram_id", tgId).eq("arxiv", false).maybeSingle();

  if (isKeldi) {
    await sb.from("davomat").upsert({
      telegram_id: tgId, sana, keldi: now.toISOString(), lat, lng, masofa_m: masofa,
      video_file_id: fileId, is_sinov: !!sinovAktiv, holat: minutesOfDay(now) > 540 ? "Kech qoldi" : "Vaqtida",
    }, { onConflict: "telegram_id,sana" });
  } else {
    await sb.from("davomat").update({
      ketdi: now.toISOString(), video_file_id: fileId,
    }).eq("telegram_id", tgId).eq("sana", sana);
  }
  await clearSess(tgId);
  await ctx.reply("Qabul qilindi.", { reply_markup: await mainMenu(x) });

  const target = await xulosaTarget();
  if (target) {
    await bot.api.sendVideoNote(target.chatId, fileId, { message_thread_id: target.topic }).catch(() => {});
    let holat: string;
    if (isKeldi) {
      const min = minutesOfDay(now);
      if (min < 540) holat = `ishga erta keldi (+${540 - min} daqiqa)`;
      else if (min === 540) holat = "ishga keldi";
      else holat = `ishga kech keldi (+${min - 540} daqiqa)`;
    } else {
      holat = "ishdan ketdi";
    }
    const text = davomatXabarMatn({
      bolim: x.bolim ?? "", ism: x.ism, holat, vaqt: timeHms(now), sana: todayTashkent(),
      maps: `https://www.google.com/maps?q=${lat},${lng}`,
    });
    await bot.api.sendMessage(target.chatId, text, { message_thread_id: target.topic, parse_mode: "HTML" }).catch(() => {});
  }
});

// ── XODIMLAR ────────────────────────────────────────────────────────
bot.hears(BTN_XODIMLAR, async (ctx) => {
  const x = await getXodim(ctx.from!.id);
  if (!x || !(await isBoshqaruvchi(x))) return ctx.reply("Sizda bu bo'limga kirish huquqi yo'q.");
  const { data: list } = await sb.from("xodimlar").select("ism,rol,bolim").eq("arxiv", false)
    .order("bolim", { ascending: true, nullsFirst: false }).order("ism");
  let txt = "<b>Xodimlar ro'yxati</b>\n\n";
  let oxirgiBolim: string | undefined;
  (list ?? []).forEach((r) => {
    const b = r.bolim || "Bo'limsiz";
    if (b !== oxirgiBolim) { txt += `<b>— ${escHtml(b)} —</b>\n`; oxirgiBolim = b; }
    txt += `${escHtml(r.ism)} — ${escHtml(r.rol)}\n`;
  });
  const kb = new InlineKeyboard().text("Qo'shish", "xod:add").text("Arxivlash", "xod:arx").row().text("Bo'limlar", "bol:list");
  await ctx.reply(txt || "Xodimlar yo'q.", { parse_mode: "HTML", reply_markup: kb });
});

bot.callbackQuery("xod:add", async (ctx) => {
  await ctx.answerCallbackQuery();
  const x = await getXodim(ctx.from!.id);
  if (!x || !(await isBoshqaruvchi(x))) return;
  await setSess(ctx.from!.id, "xodim_add_ism", {});
  await ctx.reply("Xodimning to'liq ismini yuboring:", { reply_markup: new Keyboard().text(BTN_BEKOR).resized() });
});

bot.callbackQuery("xod:arx", async (ctx) => {
  await ctx.answerCallbackQuery();
  const x = await getXodim(ctx.from!.id);
  if (!x || !(await isBoshqaruvchi(x))) return;
  const { data: list } = await sb.from("xodimlar").select("telegram_id,ism").eq("arxiv", false).order("ism");
  const kb = new InlineKeyboard();
  (list ?? []).forEach((r) => kb.text(r.ism, `xod:arxq:${r.telegram_id}`).row());
  await ctx.reply("Kimni arxivlaymiz?", { reply_markup: kb });
});

bot.callbackQuery(/^xod:arxq:(\d+)$/, async (ctx) => {
  await ctx.answerCallbackQuery();
  const x = await getXodim(ctx.from!.id);
  if (!x || !(await isBoshqaruvchi(x))) return;
  const tgId = parseInt(ctx.match![1]);
  await sb.from("xodimlar").update({ arxiv: true, arxiv_sana: todayTashkent() }).eq("telegram_id", tgId);
  await ctx.reply("Arxivlandi.");
});

// ── BO'LIMLAR ──────────────────────────────────────────────────────
bot.callbackQuery("bol:list", async (ctx) => {
  await ctx.answerCallbackQuery();
  const x = await getXodim(ctx.from!.id);
  if (!x || !(await isBoshqaruvchi(x))) return;
  const { data: list } = await sb.from("bolimlar").select("nom").eq("arxiv", false).order("nom");
  let txt = "<b>Bo'limlar</b>\n\n";
  (list ?? []).forEach((r, i) => { txt += `${i + 1}. ${escHtml(r.nom)}\n`; });
  const kb = new InlineKeyboard().text("+ Yangi bo'lim", "bol:add").row().text("Arxivlash", "bol:arx");
  await ctx.reply(txt || "Bo'limlar yo'q.", { parse_mode: "HTML", reply_markup: kb });
});

bot.callbackQuery("bol:add", async (ctx) => {
  await ctx.answerCallbackQuery();
  const x = await getXodim(ctx.from!.id);
  if (!x || !(await isBoshqaruvchi(x))) return;
  await setSess(ctx.from!.id, "bolim_add_nom", {});
  await ctx.reply("Yangi bo'lim nomini yuboring:", { reply_markup: new Keyboard().text(BTN_BEKOR).resized() });
});

bot.callbackQuery("bol:arx", async (ctx) => {
  await ctx.answerCallbackQuery();
  const x = await getXodim(ctx.from!.id);
  if (!x || !(await isBoshqaruvchi(x))) return;
  const { data: list } = await sb.from("bolimlar").select("id,nom").eq("arxiv", false).order("nom");
  const kb = new InlineKeyboard();
  (list ?? []).forEach((r) => kb.text(r.nom, `bol:arxq:${r.id}`).row());
  await ctx.reply("Qaysi bo'limni arxivlaymiz?", { reply_markup: kb });
});

bot.callbackQuery(/^bol:arxq:(\d+)$/, async (ctx) => {
  await ctx.answerCallbackQuery();
  const x = await getXodim(ctx.from!.id);
  if (!x || !(await isBoshqaruvchi(x))) return;
  const id = parseInt(ctx.match![1]);
  await sb.from("bolimlar").update({ arxiv: true }).eq("id", id);
  await ctx.reply("Arxivlandi.");
});

const BOLIM_YOQ = "_yoq_";

async function bolimTanlashKb(prefix: string): Promise<InlineKeyboard> {
  const { data: list } = await sb.from("bolimlar").select("nom").eq("arxiv", false).order("nom");
  const kb = new InlineKeyboard();
  (list ?? []).forEach((r) => kb.text(r.nom, `${prefix}:${r.nom}`).row());
  kb.text("Bo'limsiz", `${prefix}:${BOLIM_YOQ}`);
  return kb;
}

async function rolTanlashKb(prefix: string): Promise<InlineKeyboard> {
  const { data: rollar } = await sb.from("rollar").select("nom").order("nom");
  const kb = new InlineKeyboard();
  (rollar ?? []).forEach((r) => kb.text(r.nom, `${prefix}:${r.nom}`).row());
  return kb;
}

// ── SINOV ──────────────────────────────────────────────────────────
bot.hears(BTN_SINOV, async (ctx) => {
  const x = await getXodim(ctx.from!.id);
  if (!x) return;
  const h = await getHuquq(x.rol);
  if (!x.super_admin && !h?.sinov_boshqaradi) return ctx.reply("Sizda bu bo'limga kirish huquqi yo'q.");
  const { data: list } = await sb.from("sinov").select("id,ism,bosqich,natija,boshlanish,tugash_max").eq("arxiv", false).order("ism");
  let txt = "<b>Sinovdagi xodimlar</b>\n\n";
  const kb = new InlineKeyboard();
  (list ?? []).forEach((r, i) => {
    txt += `${i + 1}. <b>${escHtml(r.ism)}</b> — ${r.bosqich} — ${r.natija ?? "Kutilmoqda"} (${r.boshlanish} → ${r.tugash_max})\n`;
    kb.text(r.ism, `snv:${r.id}`).row();
  });
  kb.text("+ Yangi sinov qo'shish", "snv:add");
  await ctx.reply(txt, { parse_mode: "HTML", reply_markup: kb });
});

bot.callbackQuery("snv:add", async (ctx) => {
  await ctx.answerCallbackQuery();
  await setSess(ctx.from!.id, "sinov_add_ism", {});
  await ctx.reply("Sinovchi to'liq ismini yuboring:", { reply_markup: new Keyboard().text(BTN_BEKOR).resized() });
});

bot.callbackQuery(/^snv:bolim:(.+)$/, async (ctx) => {
  await ctx.answerCallbackQuery();
  const bolim = ctx.match![1] === BOLIM_YOQ ? null : ctx.match![1];
  const sess = await getSess(ctx.from!.id);
  await setSess(ctx.from!.id, "sinov_add_summa", { ...sess.data, bolim });
  await ctx.reply("Sinov davri uchun umumiy summani kiriting (so'mda, masalan 400000):");
});

bot.callbackQuery(/^snv:(\d+)$/, async (ctx) => {
  await ctx.answerCallbackQuery();
  const id = ctx.match![1];
  const kb = new InlineKeyboard()
    .text("Adaptatsiya", `snv:bosqich:${id}:Adaptatsiya`).text("Sinov+Imtihon", `snv:bosqich:${id}:Sinov+Imtihon`).row()
    .text("Qabul", `snv:natija:${id}:Qabul`).text("Rad", `snv:natija:${id}:Rad`).row();
  await ctx.reply("Amalni tanlang:", { reply_markup: kb });
});

bot.callbackQuery(/^snv:bosqich:(\d+):(.+)$/, async (ctx) => {
  await ctx.answerCallbackQuery("Yangilandi");
  const [, id, val] = ctx.match!;
  await sb.from("sinov").update({ bosqich: val }).eq("id", id);
  await ctx.reply(`Bosqich: ${val} qilib belgilandi.`);
});

bot.callbackQuery(/^snv:natija:(\d+):(.+)$/, async (ctx) => {
  await ctx.answerCallbackQuery("Yangilandi");
  const [, id, val] = ctx.match!;
  const { data: s } = await sb.from("sinov").select("telegram_id").eq("id", id).maybeSingle();
  await sb.from("sinov").update({ natija: val, arxiv: val !== "Kutilmoqda" }).eq("id", id);
  if (val === "Qabul" && s?.telegram_id) {
    await sb.from("xodimlar").update({ hisobga_olinmaydi: false }).eq("telegram_id", s.telegram_id);
  }
  await ctx.reply(`Natija: ${val} qilib belgilandi.`);
});

// ── HISOBOT (davr tanlash -> format tanlash) ───────────────────────
bot.hears(BTN_HISOBOT, async (ctx) => {
  const x = await getXodim(ctx.from!.id);
  if (!x) return;
  const h = await getHuquq(x.rol);
  if (!x.super_admin && !h?.hisobot_koradi) return ctx.reply("Sizda bu bo'limga kirish huquqi yo'q.");
  const kb = new InlineKeyboard()
    .text("Bugun", "hsb:d:bugun").text("Hafta", "hsb:d:hafta").row()
    .text("Oy", "hsb:d:oy").text("Yil", "hsb:d:yil").row()
    .text("Maxsus oraliq", "hsb:d:maxsus");
  await ctx.reply("Davrni tanlang:", { reply_markup: kb });
});

function davrOraliq(kod: string): { boshlanish: string; tugash: string } | null {
  const bugun = new Date();
  const p = tashkentParts(bugun);
  const todayISO = `${p.year}-${p.month}-${p.day}`;
  const today = new Date(`${todayISO}T00:00:00Z`);
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  if (kod === "bugun") return { boshlanish: todayISO, tugash: todayISO };
  if (kod === "hafta") {
    const day = today.getUTCDay() || 7;
    const mon = new Date(today); mon.setUTCDate(today.getUTCDate() - day + 1);
    return { boshlanish: fmt(mon), tugash: todayISO };
  }
  if (kod === "oy") return { boshlanish: `${p.year}-${p.month}-01`, tugash: todayISO };
  if (kod === "yil") return { boshlanish: `${p.year}-01-01`, tugash: todayISO };
  return null;
}

bot.callbackQuery(/^hsb:d:(bugun|hafta|oy|yil)$/, async (ctx) => {
  await ctx.answerCallbackQuery();
  const oraliq = davrOraliq(ctx.match![1])!;
  await setSess(ctx.from!.id, "hisobot_fmt", { boshlanish: oraliq.boshlanish, tugash: oraliq.tugash });
  const kb = new InlineKeyboard()
    .text("Matn", "hsb:f:matn").text("Rasm", "hsb:f:rasm").row()
    .text("Excel", "hsb:f:excel").text("PDF", "hsb:f:pdf");
  await ctx.reply("Formatni tanlang:", { reply_markup: kb });
});

bot.callbackQuery("hsb:d:maxsus", async (ctx) => {
  await ctx.answerCallbackQuery();
  await setSess(ctx.from!.id, "hisobot_maxsus_boshlanish", {});
  await ctx.reply("Boshlanish sanasini yuboring (YYYY-MM-DD):", { reply_markup: new Keyboard().text(BTN_BEKOR).resized() });
});

async function hisobotGenerate(chatId: number, boshlanish: string, tugash: string) {
  const { data: rows } = await sb.rpc("davomat_oraliq", { p_boshlanish: boshlanish, p_tugash: tugash });
  const list = (rows ?? []) as { ism: string; bolim: string | null; kelgan_kun: number; jami_soat: number; kech_soni: number }[];
  let txt = `<b>DAVOMAT HISOBOTI</b>\n${boshlanish} — ${tugash}\n\n`;
  let oxirgiBolim: string | undefined;
  list.forEach((r) => {
    const b = r.bolim || "Bo'limsiz";
    if (b !== oxirgiBolim) { txt += `<b>— ${escHtml(b)} —</b>\n`; oxirgiBolim = b; }
    txt += `${escHtml(r.ism)} — ${r.kelgan_kun} kun, ${r.jami_soat} soat (kech: ${r.kech_soni})\n`;
  });
  await bot.api.sendMessage(chatId, txt, { parse_mode: "HTML" });
}

bot.callbackQuery(/^hsb:f:(matn|rasm|excel|pdf)$/, async (ctx) => {
  await ctx.answerCallbackQuery();
  const sess = await getSess(ctx.from!.id);
  const boshlanish = sess.data.boshlanish as string, tugash = sess.data.tugash as string;
  await clearSess(ctx.from!.id);
  const fmt = ctx.match![1];
  await ctx.reply("Tayyorlanmoqda...");

  if (fmt === "matn") {
    await hisobotGenerate(ctx.chat!.id, boshlanish, tugash);
    return;
  }

  const bitKun = boshlanish === tugash; // "Bugun" yoki maxsus bitta kun — batafsil (keldi/ketdi vaqti) ko'rinish
  if (bitKun) {
    // Har doim so'rov paytidagi JONLI holat (view'dan to'g'ridan-to'g'ri o'qiladi, kesh yo'q) —
    // masalan tushlik vaqtida so'ralsa, o'sha ondagi haqiqiy holatni beradi.
    const { data: kunData } = await sb.from("v_davomat_kun").select("ism,bolim,keldi,ketdi,sof_min,holat").eq("sana", tugash)
      .order("bolim", { ascending: true, nullsFirst: false }).order("ism");
    const rows: DavomatRow[] = (kunData ?? []).map((r) => ({
      ism: r.ism,
      bolim: r.bolim,
      keldi: r.keldi ? timeHms(new Date(r.keldi)) : "—",
      ketdi: r.ketdi ? timeHms(new Date(r.ketdi)) : "—",
      soat: r.keldi ? Math.round((r.sof_min / 60) * 10) / 10 : null,
      holat: r.holat,
    }));
    if (fmt === "rasm") {
      const png = await davomatPng(tugash, rows);
      await bot.api.sendPhoto(ctx.chat!.id, new InputFile(png, "davomat.png"));
    } else if (fmt === "excel") {
      const xrows: DavomatXRow[] = rows.map((r) => ({ ism: r.ism, bolim: r.bolim, keldi: r.keldi, ketdi: r.ketdi, soat: r.soat, holat: r.holat }));
      const xlsx = await davomatXlsx(tugash, xrows);
      await bot.api.sendDocument(ctx.chat!.id, new InputFile(xlsx, `davomat_${tugash}.xlsx`));
    } else if (fmt === "pdf") {
      const png = await davomatPng(tugash, rows);
      const pdf = await pngToPdf(png, 1452, 1180);
      await bot.api.sendDocument(ctx.chat!.id, new InputFile(pdf, `davomat_${tugash}.pdf`));
    }
    return;
  }

  // Ko'p kunlik davr (Hafta/Oy/Yil/Maxsus) — davomat_oraliq RPC orqali jonli agregatsiya
  const { data: oraliqData } = await sb.rpc("davomat_oraliq", { p_boshlanish: boshlanish, p_tugash: tugash });
  const rows: DavomatOraliqRow[] = ((oraliqData ?? []) as { ism: string; bolim: string | null; kelgan_kun: number; jami_soat: number; kech_soni: number }[])
    .map((r) => ({ ism: r.ism, bolim: r.bolim, kelgan_kun: r.kelgan_kun, jami_soat: Number(r.jami_soat), kech_soni: r.kech_soni }));

  if (fmt === "rasm") {
    const png = await davomatOraliqPng(boshlanish, tugash, rows);
    await bot.api.sendPhoto(ctx.chat!.id, new InputFile(png, "davomat.png"));
  } else if (fmt === "excel") {
    const xrows: DavomatOraliqXRow[] = rows.map((r) => ({ ism: r.ism, bolim: r.bolim, kelgan_kun: r.kelgan_kun, jami_soat: r.jami_soat, kech_soni: r.kech_soni }));
    const xlsx = await davomatOraliqXlsx(boshlanish, tugash, xrows);
    await bot.api.sendDocument(ctx.chat!.id, new InputFile(xlsx, `davomat_${boshlanish}_${tugash}.xlsx`));
  } else if (fmt === "pdf") {
    const png = await davomatOraliqPng(boshlanish, tugash, rows);
    const pdf = await pngToPdf(png, 1452, Math.max(700, 260 + rows.length * 48));
    await bot.api.sendDocument(ctx.chat!.id, new InputFile(pdf, `davomat_${boshlanish}_${tugash}.pdf`));
  }
});

// ── MAOSH ──────────────────────────────────────────────────────────
bot.hears(BTN_MAOSH, async (ctx) => {
  const x = await getXodim(ctx.from!.id);
  if (!x) return;
  const h = await getHuquq(x.rol);
  if (!x.super_admin && !h?.maosh_koradi) return ctx.reply("Sizda bu bo'limga kirish huquqi yo'q.");
  const p = tashkentParts(new Date());
  const oy = `${p.year}-${p.month}`;
  const { data: rows } = await sb.rpc("maosh_oylik", { p_oy: oy });
  const list = (rows ?? []) as { ism: string; rol: string; jami_soat: number; baza: number; ovqat: number; bonus: number; yakuniy: number }[];
  let txt = `<b>OYLIK MAOSH</b> — ${oy}\n\n`;
  let jami = 0;
  list.forEach((r) => {
    jami += Number(r.yakuniy);
    txt += `<b>${escHtml(r.ism)}</b> (${escHtml(r.rol)}) — ${r.yakuniy.toLocaleString()} som, ${r.jami_soat} soat\n`;
  });
  txt += `\n<b>Jami:</b> ${jami.toLocaleString()} som`;
  const kb = new InlineKeyboard().text("Excel", `mao:excel:${oy}`).text("PDF", `mao:pdf:${oy}`);
  await ctx.reply(txt, { parse_mode: "HTML", reply_markup: kb });
});

bot.callbackQuery(/^mao:(excel|pdf):(.+)$/, async (ctx) => {
  await ctx.answerCallbackQuery();
  const [, fmt, oy] = ctx.match!;
  const { data: rows } = await sb.rpc("maosh_oylik", { p_oy: oy });
  const mrows: MaoshXRow[] = ((rows ?? []) as { ism: string; rol: string; jami_soat: number; baza: number; ovqat: number; bonus: number; yakuniy: number }[]).map((r) => ({
    ism: r.ism, rol: r.rol, jami_soat: r.jami_soat, baza: r.baza + (r.ovqat || 0), bonus: r.bonus, yakuniy: r.yakuniy,
  }));
  if (fmt === "excel") {
    const xlsx = await maoshXlsx(oy, mrows);
    await bot.api.sendDocument(ctx.chat!.id, new InputFile(xlsx, `maosh_${oy}.xlsx`));
  } else {
    const pdf = await maoshPdf(oy, mrows);
    await bot.api.sendDocument(ctx.chat!.id, new InputFile(pdf, `maosh_${oy}.pdf`));
  }
});

// ── SOZLAMALAR ─────────────────────────────────────────────────────
bot.hears(BTN_SOZLAMALAR, async (ctx) => {
  const x = await getXodim(ctx.from!.id);
  if (!x) return;
  const h = await getHuquq(x.rol);
  if (!x.super_admin && !h?.sozlama_boshqaradi) return ctx.reply("Sizda bu bo'limga kirish huquqi yo'q.");
  const keys = ["signal_qabul", "xulosa_group_id", "xulosa_topic_id", "anomaliya_kun", "ofis_radius_m"];
  let txt = "<b>Joriy sozlamalar</b>\n\n";
  for (const k of keys) txt += `<b>${k}:</b> ${escHtml((await getConfig(k)) ?? "-")}\n`;
  const kb = new InlineKeyboard();
  keys.forEach((k) => kb.text(k, `set:${k}`).row());
  if (x.super_admin) kb.text("Super admin qo'shish", "set:superadmin");
  await ctx.reply(txt, { parse_mode: "HTML", reply_markup: kb });
});

bot.callbackQuery(/^set:([a-z_]+)$/, async (ctx) => {
  await ctx.answerCallbackQuery();
  const key = ctx.match![1];
  const x = await getXodim(ctx.from!.id);
  if (!x) return;
  const h = await getHuquq(x.rol);
  if (!x.super_admin && !h?.sozlama_boshqaradi) return;
  if (key === "superadmin") {
    if (!x.super_admin) return ctx.reply("Faqat super admin boshqa super admin qo'sha oladi.");
    await setSess(ctx.from!.id, "superadmin_tgid", {});
    await ctx.reply("Yangi super adminning Telegram ID raqamini yuboring (u avval xodim sifatida qo'shilgan bo'lishi kerak):", {
      reply_markup: new Keyboard().text(BTN_BEKOR).resized(),
    });
    return;
  }
  await setSess(ctx.from!.id, "sozlama_qiymat", { key });
  await ctx.reply(`"${key}" uchun yangi qiymatni yuboring:`, { reply_markup: new Keyboard().text(BTN_BEKOR).resized() });
});

// ── Bosqichli matn kirituvlar (step-based) ─────────────────────────
bot.on("message:text", async (ctx) => {
  const tgId = ctx.from!.id;
  const text = ctx.message.text.trim();
  const sess = await getSess(tgId);
  if (!sess.step) return;

  if (sess.step === "xodim_add_ism") {
    await setSess(tgId, "xodim_add_tgid", { ism: text });
    await ctx.reply("Uning Telegram ID raqamini yuboring (masalan @userinfobot orqali oling):");
    return;
  }
  if (sess.step === "xodim_add_tgid") {
    const id = parseInt(text);
    if (!id || isNaN(id)) return ctx.reply("Raqam noto'g'ri. Faqat Telegram ID raqamini yuboring.");
    await setSess(tgId, "xodim_add_bolim", { ...sess.data, telegram_id: id });
    await ctx.reply("Bo'limini tanlang:", { reply_markup: await bolimTanlashKb("xod:bolim") });
    return;
  }
  if (sess.step === "sinov_add_ism") {
    await setSess(tgId, "sinov_add_tgid", { ism: text });
    await ctx.reply("Sinovchining Telegram ID raqamini yuboring:");
    return;
  }
  if (sess.step === "sinov_add_tgid") {
    const id = parseInt(text);
    if (!id || isNaN(id)) return ctx.reply("Raqam noto'g'ri. Qaytadan yuboring.");
    await setSess(tgId, "sinov_add_bolim", { ...sess.data, telegram_id: id });
    await ctx.reply("Bo'limini tanlang:", { reply_markup: await bolimTanlashKb("snv:bolim") });
    return;
  }
  if (sess.step === "bolim_add_nom") {
    const { error } = await sb.from("bolimlar").insert({ nom: text });
    await clearSess(tgId);
    const x = await getXodim(tgId);
    if (error) {
      await ctx.reply(`Xatolik: "${text}" bo'limi allaqachon mavjud bo'lishi mumkin.`, { reply_markup: x ? await mainMenu(x) : undefined });
    } else {
      await ctx.reply(`Bo'lim qo'shildi: ${text}`, { reply_markup: x ? await mainMenu(x) : undefined });
    }
    return;
  }
  if (sess.step === "sinov_add_summa") {
    const summa = parseInt(text.replace(/\D/g, ""));
    if (!summa) return ctx.reply("Summa noto'g'ri. Qaytadan kiriting.");
    const d = sess.data as { ism: string; telegram_id: number; bolim: string };
    const boshlanish = todayTashkent();
    const tugashD = new Date(); tugashD.setUTCDate(tugashD.getUTCDate() + 18);
    const tugash_max = tugashD.toISOString().slice(0, 10);
    await sb.from("xodimlar").upsert({
      telegram_id: d.telegram_id, ism: d.ism, bolim: d.bolim, rol: "Sotuvchi",
    }, { onConflict: "telegram_id" });
    await sb.from("sinov").insert({
      telegram_id: d.telegram_id, ism: d.ism, bolim: d.bolim,
      boshlanish, tugash_max, summa_umumiy: summa, bosqich: "Adaptatsiya",
    });
    await clearSess(tgId);
    const x = await getXodim(tgId);
    await ctx.reply(`Sinov qo'shildi: ${d.ism} — ${summa.toLocaleString()} so'm.`, { reply_markup: x ? await mainMenu(x) : undefined });
    return;
  }
  if (sess.step === "hisobot_maxsus_boshlanish") {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) return ctx.reply("Format: YYYY-MM-DD. Qaytadan yuboring.");
    await setSess(tgId, "hisobot_maxsus_tugash", { boshlanish: text });
    await ctx.reply("Tugash sanasini yuboring (YYYY-MM-DD):");
    return;
  }
  if (sess.step === "hisobot_maxsus_tugash") {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) return ctx.reply("Format: YYYY-MM-DD. Qaytadan yuboring.");
    const boshlanish = sess.data.boshlanish as string;
    await setSess(tgId, "hisobot_fmt", { boshlanish, tugash: text });
    const kb = new InlineKeyboard()
      .text("Matn", "hsb:f:matn").text("Rasm", "hsb:f:rasm").row()
      .text("Excel", "hsb:f:excel").text("PDF", "hsb:f:pdf");
    await ctx.reply("Formatni tanlang:", { reply_markup: kb });
    return;
  }
  if (sess.step === "sozlama_qiymat") {
    const key = (sess.data as { key: string }).key;
    await setConfig(key, text);
    await clearSess(tgId);
    const x = await getXodim(tgId);
    await ctx.reply(`"${key}" yangilandi: ${text}`, { reply_markup: x ? await mainMenu(x) : undefined });
    return;
  }
  if (sess.step === "superadmin_tgid") {
    const id = parseInt(text);
    if (!id || isNaN(id)) return ctx.reply("Raqam noto'g'ri.");
    const { data: target } = await sb.from("xodimlar").select("telegram_id,ism").eq("telegram_id", id).eq("arxiv", false).maybeSingle();
    if (!target) {
      await ctx.reply("Bu ID xodimlar ro'yxatida topilmadi. Avval uni 'Xodimlar' bo'limidan qo'shing.");
      return;
    }
    await sb.from("xodimlar").update({ super_admin: true }).eq("telegram_id", id);
    await clearSess(tgId);
    const x = await getXodim(tgId);
    await ctx.reply(`${target.ism} endi super admin.`, { reply_markup: x ? await mainMenu(x) : undefined });
    return;
  }
});

bot.callbackQuery(/^xod:bolim:(.+)$/, async (ctx) => {
  await ctx.answerCallbackQuery();
  const bolim = ctx.match![1] === BOLIM_YOQ ? null : ctx.match![1];
  const sess = await getSess(ctx.from!.id);
  await setSess(ctx.from!.id, "xodim_add_rol", { ...sess.data, bolim });
  await ctx.reply("Rolini tanlang:", { reply_markup: await rolTanlashKb("xod:rol") });
});

bot.callbackQuery(/^xod:rol:(.+)$/, async (ctx) => {
  await ctx.answerCallbackQuery();
  const rol = ctx.match![1];
  const sess = await getSess(ctx.from!.id);
  const d = sess.data as { ism: string; telegram_id: number; bolim: string | null };
  await sb.from("xodimlar").upsert({
    telegram_id: d.telegram_id, ism: d.ism, bolim: d.bolim, rol,
  }, { onConflict: "telegram_id" });
  await clearSess(ctx.from!.id);
  const x = await getXodim(ctx.from!.id);
  await ctx.reply(`Xodim qo'shildi: ${d.ism} (${rol}).`, { reply_markup: x ? await mainMenu(x) : undefined });
});

  return bot;
}

let botPromise: Promise<Bot> = initBot();

Deno.serve(async (req) => {
  if (req.method !== "POST" || req.headers.get("content-length") === "0") {
    return new Response("ok");
  }
  try {
    const bot = await botPromise;
    const handleUpdate = webhookCallback(bot, "std/http");
    return await handleUpdate(req);
  } catch (e) {
    console.error(e);
    botPromise = initBot(); // keyingi so'rov qayta urinsin, funksiya abadiy "qulab" qolmasin
    return new Response("ok"); // Telegramga har doim 200 qaytaramiz, qayta-qayta urinmasin
  }
});
IMEDHRBOT_INDEX_EOF

cat > render.ts <<'IMEDHRBOT_RENDER_EOF'
// iMed HR bot — vizual dashboard PNG (Satori + resvg-wasm, edge ichida)
import satori from "npm:satori@0.10.13";
import { html } from "npm:satori-html@0.3.2";
import { initWasm, Resvg } from "npm:@resvg/resvg-wasm@2.6.2";

const WASM_URL = "https://unpkg.com/@resvg/resvg-wasm@2.6.2/index_bg.wasm";
const FONT_REG = "https://cdn.jsdelivr.net/npm/@fontsource/noto-sans/files/noto-sans-latin-ext-400-normal.woff";
const FONT_BOLD = "https://cdn.jsdelivr.net/npm/@fontsource/noto-sans/files/noto-sans-latin-ext-700-normal.woff";

let fontReg: ArrayBuffer | null = null;
let fontBold: ArrayBuffer | null = null;
let readyPromise: Promise<void> | null = null;

async function _init() {
  const [wasm, fr, fb] = await Promise.all([
    fetch(WASM_URL).then((r) => r.arrayBuffer()),
    fetch(FONT_REG).then((r) => r.arrayBuffer()),
    fetch(FONT_BOLD).then((r) => r.arrayBuffer()),
  ]);
  await initWasm(wasm);
  fontReg = fr;
  fontBold = fb;
}
function ensureReady(): Promise<void> {
  if (!readyPromise) readyPromise = _init().catch((e) => { readyPromise = null; throw e; });
  return readyPromise;
}

function esc(s: unknown): string {
  return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

async function toPng(markup: string, width: number, height: number): Promise<Uint8Array> {
  await ensureReady();
  const svg = await satori(html(markup), {
    width, height,
    fonts: [
      { name: "Noto Sans", data: fontReg!, weight: 400, style: "normal" },
      { name: "Noto Sans", data: fontBold!, weight: 700, style: "normal" },
    ],
  });
  // 1x render (edge CPU/xotira chegarasi uchun) — Telegram'da baribir tiniq
  const png = new Resvg(svg, {
    background: "#E7EFF8",
    fitTo: { mode: "width", value: width },
  }).render().asPng();
  return png;
}

const PCT: Record<string, [string, string]> = {
  ok: ["#E4F5EA", "#2E9E5B"], warn: ["#FDF0DE", "#E6902A"],
  bad: ["#FBE7EB", "#D5556A"], auto: ["#E7F0FB", "#2E86D6"],
};
function holatKey(h: string | null): string {
  if (!h) return "bad";
  if (h === "Kech qoldi") return "warn";
  if (h === "Avtomatik") return "auto";
  return "ok";
}
function gauge(pct: number): string {
  const r = 64, c = 2 * Math.PI * r, off = c * (1 - pct / 100);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="150" height="150" viewBox="0 0 150 150">
    <circle cx="75" cy="75" r="64" fill="none" stroke="#E8EEF5" stroke-width="16"/>
    <circle cx="75" cy="75" r="64" fill="none" stroke="#2AA84F" stroke-width="16" stroke-linecap="round"
      stroke-dasharray="${c}" stroke-dashoffset="${off}" transform="rotate(-90 75 75)"/></svg>`;
  return "data:image/svg+xml;utf8," + encodeURIComponent(svg);
}
const CARD = "background:white;border-radius:18px;box-shadow:0 6px 20px rgba(20,60,110,0.10);padding:22px 24px;display:flex;";

export interface DavomatRow { ism: string; bolim?: string | null; keldi: string; ketdi: string; soat: number | null; holat: string | null; }

function bolimHeaderRow(bolim: string): string {
  return `<div style="display:flex;align-items:center;padding:7px 14px;background:#DCEAFB;">
    <div style="display:flex;font-size:12px;font-weight:700;color:#0E2A47;letter-spacing:0.5px;">${esc(bolim.toUpperCase())}</div>
  </div>`;
}
function groupedRowsHtml<T extends { bolim?: string | null }>(rows: T[], tr: (r: T, i: number) => string): string {
  let oxirgiBolim: string | undefined;
  return rows.map((r, i) => {
    const b = r.bolim || "Bo'limsiz";
    let html = "";
    if (b !== oxirgiBolim) { html += bolimHeaderRow(b); oxirgiBolim = b; }
    return html + tr(r, i);
  }).join("");
}

export async function davomatPng(sana: string, rows: DavomatRow[]): Promise<Uint8Array> {
  const present = rows.filter((r) => r.holat && r.soat !== null);
  const kelgan = present.length;
  const jami = rows.length;
  const pct = jami ? Math.round((kelgan / jami) * 100) : 0;
  const jamiSoat = present.reduce((s, r) => s + (r.soat || 0), 0);
  const ort = kelgan ? (jamiSoat / kelgan).toFixed(1) : "0";
  const kech = rows.filter((r) => r.holat === "Kech qoldi").length;
  const vaqtida = rows.filter((r) => r.holat === "Vaqtida").length;
  const maxSoat = Math.max(1, ...present.map((r) => r.soat || 0));
  const bars = [...present].sort((a, b) => (b.soat || 0) - (a.soat || 0)).slice(0, 10);

  const th = (t: string, w: string, al = "flex-start") =>
    `<div style="display:flex;width:${w};justify-content:${al};font-size:14px;font-weight:700;color:white;">${t}</div>`;
  const tr = (r: DavomatRow, i: number) => {
    const [bg, fg] = PCT[holatKey(r.holat)];
    const label = r.holat ?? "Kelmadi";
    const soat = r.soat === null ? "—" : r.soat.toFixed(1);
    return `<div style="display:flex;align-items:center;padding:12px 14px;background:${i % 2 ? "#F7FAFD" : "#FFFFFF"};border-bottom:1px solid #E5EBF2;">
      <div style="display:flex;width:210px;font-size:15px;font-weight:700;color:#0E2A47;">${esc(r.ism)}</div>
      <div style="display:flex;width:85px;font-size:15px;color:#1B2B41;">${esc(r.keldi)}</div>
      <div style="display:flex;width:85px;font-size:15px;color:#1B2B41;">${esc(r.ketdi)}</div>
      <div style="display:flex;width:64px;font-size:15px;font-weight:700;color:#1B2B41;justify-content:flex-end;">${soat}</div>
      <div style="display:flex;flex:1;justify-content:flex-end;"><div style="display:flex;background:${bg};color:${fg};font-size:13px;font-weight:700;padding:4px 12px;border-radius:20px;">${esc(label)}</div></div>
    </div>`;
  };
  const bar = (r: DavomatRow) => {
    const w = Math.round(((r.soat || 0) / maxSoat) * 100);
    return `<div style="display:flex;align-items:center;">
      <div style="display:flex;width:170px;justify-content:flex-end;font-size:15px;font-weight:600;color:#1B2B41;padding-right:12px;">${esc(r.ism)}</div>
      <div style="display:flex;flex:1;height:22px;background:#EEF3F8;border-radius:8px;"><div style="display:flex;width:${w}%;height:22px;background:linear-gradient(90deg,#2E86D6,#1466B8);border-radius:8px;"></div></div>
      <div style="display:flex;width:56px;justify-content:flex-end;font-size:15px;font-weight:700;color:#0E2A47;">${(r.soat || 0).toFixed(1)}</div>
    </div>`;
  };

  const markup = `<div style="display:flex;flex-direction:column;width:1400px;background:#E7EFF8;padding:26px;font-family:'Noto Sans';">
    <div style="display:flex;align-items:center;justify-content:space-between;border-radius:20px;padding:26px 34px;background:linear-gradient(100deg,#0F5FB0,#1E79C4,#2AA84F);">
      <div style="display:flex;flex-direction:column;">
        <div style="display:flex;font-size:38px;font-weight:700;color:white;">BUGUNGI DAVOMAT DASHBOARDI</div>
        <div style="display:flex;font-size:16px;color:#EAF4FF;margin-top:4px;">iMed Team · davomat nazorati</div>
      </div>
      <div style="display:flex;flex-direction:column;align-items:center;background:rgba(255,255,255,0.18);border:1px solid rgba(255,255,255,0.35);padding:12px 20px;border-radius:14px;">
        <div style="display:flex;font-size:12px;color:#EAF4FF;">SANA</div>
        <div style="display:flex;font-size:18px;font-weight:700;color:white;">${esc(sana)}</div>
      </div>
    </div>
    <div style="display:flex;gap:20px;margin-top:20px;">
      <div style="${CARD}flex:1;align-items:center;gap:24px;">
        <div style="display:flex;position:relative;width:150px;height:150px;align-items:center;justify-content:center;">
          <img src="${gauge(pct)}" width="150" height="150" style="position:absolute;top:0;left:0;" />
          <div style="display:flex;flex-direction:column;align-items:center;">
            <div style="display:flex;font-size:30px;font-weight:700;color:#0E2A47;">${kelgan}/${jami}</div>
            <div style="display:flex;font-size:13px;color:#6B7A90;">keldi</div>
          </div>
        </div>
        <div style="display:flex;flex-direction:column;">
          <div style="display:flex;font-size:19px;font-weight:600;color:#6B7A90;">KELGANLAR</div>
          <div style="display:flex;font-size:50px;font-weight:700;color:#0E2A47;">${kelgan}</div>
          <div style="display:flex;background:#E4F5EA;color:#2E9E5B;font-size:14px;font-weight:700;padding:5px 12px;border-radius:20px;margin-top:8px;">${pct}% davomat</div>
        </div>
      </div>
      <div style="${CARD}flex:1;align-items:center;">
        <div style="display:flex;flex-direction:column;">
          <div style="display:flex;font-size:19px;font-weight:600;color:#6B7A90;">O‘RTACHA ISH SOATI</div>
          <div style="display:flex;font-size:50px;font-weight:700;color:#0E2A47;">${ort}</div>
          <div style="display:flex;background:#E7F0FB;color:#2E86D6;font-size:14px;font-weight:700;padding:5px 12px;border-radius:20px;margin-top:8px;">soat / xodim</div>
        </div>
      </div>
    </div>
    <div style="display:flex;gap:20px;margin-top:20px;align-items:flex-start;">
      <div style="${CARD}flex-direction:column;flex:1;">
        <div style="display:flex;font-size:22px;font-weight:700;color:#0E2A47;margin-bottom:14px;">Davomat jadvali</div>
        <div style="display:flex;align-items:center;padding:12px 14px;border-radius:10px;background:linear-gradient(90deg,#1E79C4,#2E86D6);">
          ${th("Xodim", "210px")}${th("Keldi", "85px")}${th("Ketdi", "85px")}${th("Soat", "64px", "flex-end")}
          <div style="display:flex;flex:1;justify-content:flex-end;font-size:14px;font-weight:700;color:white;">Holat</div>
        </div>
        ${groupedRowsHtml(rows, tr)}
        <div style="display:flex;align-items:center;padding:13px 14px;background:#EAF3FC;border-top:2px solid #2E86D6;">
          <div style="display:flex;width:210px;font-size:16px;font-weight:700;color:#0E2A47;">JAMI</div>
          <div style="display:flex;flex:1;font-size:16px;font-weight:700;color:#0E2A47;">${kelgan}/${jami} keldi · ${(jamiSoat).toFixed(1)} soat</div>
        </div>
      </div>
      <div style="${CARD}flex-direction:column;flex:1;">
        <div style="display:flex;font-size:22px;font-weight:700;color:#0E2A47;margin-bottom:14px;">Ish soati — xodimlar</div>
        <div style="display:flex;flex-direction:column;gap:14px;">${bars.map(bar).join("") || '<div style="display:flex;color:#6B7A90;">Bugun hali hech kim kelmadi</div>'}</div>
        <div style="display:flex;gap:14px;margin-top:18px;">
          <div style="display:flex;flex-direction:column;flex:1;background:linear-gradient(120deg,#1E79C4,#1466B8);border-radius:14px;padding:14px 16px;">
            <div style="display:flex;font-size:13px;color:white;">Kech qolganlar</div>
            <div style="display:flex;font-size:30px;font-weight:700;color:white;">${kech}</div>
          </div>
          <div style="display:flex;flex-direction:column;flex:1;background:linear-gradient(120deg,#2FAe57,#2AA84F);border-radius:14px;padding:14px 16px;">
            <div style="display:flex;font-size:13px;color:white;">Vaqtida kelganlar</div>
            <div style="display:flex;font-size:30px;font-weight:700;color:white;">${vaqtida}</div>
          </div>
        </div>
      </div>
    </div>
  </div>`;

  return await toPng(markup, 1452, 1180);
}

export interface DavomatOraliqRow { ism: string; bolim?: string | null; kelgan_kun: number; jami_soat: number; kech_soni: number; }

export async function davomatOraliqPng(boshlanish: string, tugash: string, rows: DavomatOraliqRow[]): Promise<Uint8Array> {
  const jamiKelganKun = rows.reduce((s, r) => s + (r.kelgan_kun || 0), 0);
  const jamiSoat = rows.reduce((s, r) => s + (Number(r.jami_soat) || 0), 0);
  const jamiKech = rows.reduce((s, r) => s + (r.kech_soni || 0), 0);
  const ort = rows.length ? (jamiSoat / rows.length).toFixed(1) : "0";
  const maxSoat = Math.max(1, ...rows.map((r) => Number(r.jami_soat) || 0));
  const sorted = [...rows].sort((a, b) => Number(b.jami_soat) - Number(a.jami_soat));

  const th = (t: string, w: string, al = "flex-start") =>
    `<div style="display:flex;width:${w};justify-content:${al};font-size:14px;font-weight:700;color:white;">${t}</div>`;
  const tr = (r: DavomatOraliqRow, i: number) => {
    return `<div style="display:flex;align-items:center;padding:12px 14px;background:${i % 2 ? "#F7FAFD" : "#FFFFFF"};border-bottom:1px solid #E5EBF2;">
      <div style="display:flex;width:260px;font-size:15px;font-weight:700;color:#0E2A47;">${esc(r.ism)}</div>
      <div style="display:flex;width:120px;font-size:15px;color:#1B2B41;">${r.kelgan_kun} kun</div>
      <div style="display:flex;width:120px;font-size:15px;font-weight:700;color:#1B2B41;">${Number(r.jami_soat).toFixed(1)} soat</div>
      <div style="display:flex;flex:1;justify-content:flex-end;"><div style="display:flex;background:${r.kech_soni ? "#FDF0DE" : "#E4F5EA"};color:${r.kech_soni ? "#E6902A" : "#2E9E5B"};font-size:13px;font-weight:700;padding:4px 12px;border-radius:20px;">${r.kech_soni} marta kech</div></div>
    </div>`;
  };
  const bar = (r: DavomatOraliqRow) => {
    const w = Math.round((Number(r.jami_soat) / maxSoat) * 100);
    return `<div style="display:flex;align-items:center;">
      <div style="display:flex;width:170px;justify-content:flex-end;font-size:15px;font-weight:600;color:#1B2B41;padding-right:12px;">${esc(r.ism)}</div>
      <div style="display:flex;flex:1;height:22px;background:#EEF3F8;border-radius:8px;"><div style="display:flex;width:${w}%;height:22px;background:linear-gradient(90deg,#2E86D6,#1466B8);border-radius:8px;"></div></div>
      <div style="display:flex;width:70px;justify-content:flex-end;font-size:15px;font-weight:700;color:#0E2A47;">${Number(r.jami_soat).toFixed(1)}</div>
    </div>`;
  };

  const markup = `<div style="display:flex;flex-direction:column;width:1400px;background:#E7EFF8;padding:26px;font-family:'Noto Sans';">
    <div style="display:flex;align-items:center;justify-content:space-between;border-radius:20px;padding:26px 34px;background:linear-gradient(100deg,#0F5FB0,#1E79C4,#2AA84F);">
      <div style="display:flex;flex-direction:column;">
        <div style="display:flex;font-size:34px;font-weight:700;color:white;">DAVOMAT HISOBOTI</div>
        <div style="display:flex;font-size:16px;color:#EAF4FF;margin-top:4px;">iMed Team · ${esc(boshlanish)} — ${esc(tugash)}</div>
      </div>
    </div>
    <div style="display:flex;gap:20px;margin-top:20px;">
      <div style="${CARD}flex:1;flex-direction:column;">
        <div style="display:flex;font-size:16px;font-weight:600;color:#6B7A90;">JAMI KELGAN KUN</div>
        <div style="display:flex;font-size:42px;font-weight:700;color:#0E2A47;">${jamiKelganKun}</div>
      </div>
      <div style="${CARD}flex:1;flex-direction:column;">
        <div style="display:flex;font-size:16px;font-weight:600;color:#6B7A90;">O‘RTACHA SOAT</div>
        <div style="display:flex;font-size:42px;font-weight:700;color:#0E2A47;">${ort}</div>
      </div>
      <div style="${CARD}flex:1;flex-direction:column;">
        <div style="display:flex;font-size:16px;font-weight:600;color:#6B7A90;">KECH QOLISHLAR</div>
        <div style="display:flex;font-size:42px;font-weight:700;color:#0E2A47;">${jamiKech}</div>
      </div>
    </div>
    <div style="display:flex;gap:20px;margin-top:20px;align-items:flex-start;">
      <div style="${CARD}flex-direction:column;flex:1;">
        <div style="display:flex;font-size:22px;font-weight:700;color:#0E2A47;margin-bottom:14px;">Xodimlar bo'yicha</div>
        <div style="display:flex;align-items:center;padding:12px 14px;border-radius:10px;background:linear-gradient(90deg,#1E79C4,#2E86D6);">
          ${th("Xodim", "260px")}${th("Kelgan", "120px")}${th("Soat", "120px")}
          <div style="display:flex;flex:1;justify-content:flex-end;font-size:14px;font-weight:700;color:white;">Kech</div>
        </div>
        ${groupedRowsHtml(rows, tr)}
      </div>
      <div style="${CARD}flex-direction:column;flex:1;">
        <div style="display:flex;font-size:22px;font-weight:700;color:#0E2A47;margin-bottom:14px;">Ish soati — reyting</div>
        <div style="display:flex;flex-direction:column;gap:14px;">${sorted.slice(0, 12).map(bar).join("") || '<div style="display:flex;color:#6B7A90;">Ma\'lumot yo\'q</div>'}</div>
      </div>
    </div>
  </div>`;

  return await toPng(markup, 1452, Math.max(700, 260 + rows.length * 48));
}
IMEDHRBOT_RENDER_EOF

cat > excel.ts <<'IMEDHRBOT_EXCEL_EOF'
// iMed HR bot — rangli Excel (.xlsx) hisobotlar (exceljs).
// Dynamic import: exceljs faqat eksport bosilganda yuklanadi (cold-start yengil).

const NAVY = "FF0E2A47", NAVY2 = "FF1C3E68", HEADBLUE = "FF1E79C4";
const ORANGE_BG = "FFFCEBD6", ORANGE_FG = "FFD98324";
const OKBG = "FFE4F5EA", OKFG = "FF2E9E5B", WARNBG = "FFFDF0DE", WARNFG = "FFE6902A";
const BADBG = "FFFBE7EB", BADFG = "FFD5556A", AUTOBG = "FFE7F0FB", AUTOFG = "FF2E86D6";
const TOTBG = "FFEAF3FC", ZEBRA = "FFF7FAFD";

// deno-lint-ignore no-explicit-any
function thin(): any {
  const s = { style: "thin", color: { argb: "FFE5EBF2" } };
  return { top: s, left: s, bottom: s, right: s };
}
// deno-lint-ignore no-explicit-any
function banner(ws: any, range: string, text: string) {
  ws.mergeCells(range);
  const c = ws.getCell(range.split(":")[0]);
  c.value = text;
  c.font = { bold: true, size: 16, color: { argb: "FFFFFFFF" } };
  c.fill = { type: "pattern", pattern: "solid", fgColor: { argb: NAVY } };
  c.alignment = { vertical: "middle", horizontal: "left" };
  ws.getRow(1).height = 28;
}
// deno-lint-ignore no-explicit-any
function headerRow(row: any, bg: string) {
  row.height = 22;
  // deno-lint-ignore no-explicit-any
  row.eachCell((c: any) => {
    c.font = { bold: true, color: { argb: "FFFFFFFF" } };
    c.fill = { type: "pattern", pattern: "solid", fgColor: { argb: bg } };
    c.alignment = { horizontal: "center", vertical: "middle" };
    c.border = thin();
  });
}

// deno-lint-ignore no-explicit-any
function bolimHeaderRow(ws: any, colCount: number, bolim: string) {
  const row = ws.addRow([bolim.toUpperCase()]);
  ws.mergeCells(`A${row.number}:${String.fromCharCode(64 + colCount)}${row.number}`);
  row.getCell(1).font = { bold: true, size: 11, color: { argb: NAVY } };
  row.getCell(1).fill = { type: "pattern", pattern: "solid", fgColor: { argb: "FFDCEAFB" } };
  row.height = 18;
}

export interface MaoshXRow { ism: string; rol: string; jami_soat: number; baza: number; bonus: number; yakuniy: number; }

export async function maoshXlsx(oy: string, rows: MaoshXRow[]): Promise<Uint8Array> {
  const ExcelJS = (await import("npm:exceljs@4.4.0")).default;
  const wb = new ExcelJS.Workbook();
  const ws = wb.addWorksheet("Maosh");
  ws.columns = [{ width: 28 }, { width: 15 }, { width: 12 }, { width: 16 }, { width: 16 }, { width: 18 }];
  banner(ws, "A1:F1", `OYLIK MAOSH — ${oy}`);
  headerRow(ws.addRow(["Xodim", "Rol", "Ish soati", "Baza (so'm)", "Bonus (so'm)", "Umumiy maosh"]), NAVY2);

  rows.forEach((r, i) => {
    const row = ws.addRow([r.ism, r.rol, Number(r.jami_soat), Number(r.baza), Number(r.bonus) || 0, Number(r.yakuniy)]);
    row.height = 20;
    // deno-lint-ignore no-explicit-any
    row.eachCell((c: any) => { c.border = thin(); if (i % 2) c.fill = { type: "pattern", pattern: "solid", fgColor: { argb: ZEBRA } }; });
    row.getCell(1).font = { bold: true, color: { argb: NAVY } };
    [4, 5, 6].forEach((n) => { row.getCell(n).numFmt = "#,##0"; row.getCell(n).alignment = { horizontal: "right" }; });
    row.getCell(3).alignment = { horizontal: "center" };
    row.getCell(6).fill = { type: "pattern", pattern: "solid", fgColor: { argb: ORANGE_BG } };
    row.getCell(6).font = { bold: true, color: { argb: ORANGE_FG } };
  });

  const sum = (k: keyof MaoshXRow) => rows.reduce((s, r) => s + Number(r[k] as number), 0);
  const tot = ws.addRow(["JAMI", "", sum("jami_soat"), sum("baza"), sum("bonus"), sum("yakuniy")]);
  tot.height = 22;
  // deno-lint-ignore no-explicit-any
  tot.eachCell((c: any) => { c.font = { bold: true, color: { argb: NAVY } }; c.fill = { type: "pattern", pattern: "solid", fgColor: { argb: TOTBG } }; c.border = thin(); });
  [4, 5, 6].forEach((n) => { tot.getCell(n).numFmt = "#,##0"; tot.getCell(n).alignment = { horizontal: "right" }; });

  const buf = await wb.xlsx.writeBuffer();
  return new Uint8Array(buf as ArrayBuffer);
}

export interface DavomatOraliqXRow { ism: string; bolim?: string | null; kelgan_kun: number; jami_soat: number; kech_soni: number; }

export async function davomatOraliqXlsx(boshlanish: string, tugash: string, rows: DavomatOraliqXRow[]): Promise<Uint8Array> {
  const ExcelJS = (await import("npm:exceljs@4.4.0")).default;
  const wb = new ExcelJS.Workbook();
  const ws = wb.addWorksheet("Davomat");
  ws.columns = [{ width: 28 }, { width: 14 }, { width: 14 }, { width: 14 }];
  banner(ws, "A1:D1", `DAVOMAT HISOBOTI — ${boshlanish} - ${tugash}`);
  headerRow(ws.addRow(["Xodim", "Kelgan kun", "Jami soat", "Kech soni"]), HEADBLUE);

  let oxirgiBolim: string | undefined;
  rows.forEach((r, i) => {
    const b = r.bolim || "Bo'limsiz";
    if (b !== oxirgiBolim) { bolimHeaderRow(ws, 4, b); oxirgiBolim = b; }
    const row = ws.addRow([r.ism, r.kelgan_kun, Number(r.jami_soat), r.kech_soni]);
    row.height = 20;
    // deno-lint-ignore no-explicit-any
    row.eachCell((c: any) => { c.border = thin(); if (i % 2) c.fill = { type: "pattern", pattern: "solid", fgColor: { argb: ZEBRA } }; });
    row.getCell(1).font = { bold: true, color: { argb: NAVY } };
    [2, 3, 4].forEach((n) => { row.getCell(n).alignment = { horizontal: "center" }; });
    if (r.kech_soni > 0) {
      row.getCell(4).fill = { type: "pattern", pattern: "solid", fgColor: { argb: WARNBG } };
      row.getCell(4).font = { bold: true, color: { argb: WARNFG } };
    }
  });

  const tot = ws.addRow([
    "JAMI", rows.reduce((s, r) => s + r.kelgan_kun, 0),
    rows.reduce((s, r) => s + Number(r.jami_soat), 0), rows.reduce((s, r) => s + r.kech_soni, 0),
  ]);
  tot.height = 22;
  // deno-lint-ignore no-explicit-any
  tot.eachCell((c: any) => { c.font = { bold: true, color: { argb: NAVY } }; c.fill = { type: "pattern", pattern: "solid", fgColor: { argb: TOTBG } }; c.border = thin(); });
  [2, 3, 4].forEach((n) => tot.getCell(n).alignment = { horizontal: "center" });

  const buf = await wb.xlsx.writeBuffer();
  return new Uint8Array(buf as ArrayBuffer);
}

export interface DavomatXRow { ism: string; bolim?: string | null; keldi: string; ketdi: string; soat: number | null; holat: string | null; }

export async function davomatXlsx(sana: string, rows: DavomatXRow[]): Promise<Uint8Array> {
  const ExcelJS = (await import("npm:exceljs@4.4.0")).default;
  const wb = new ExcelJS.Workbook();
  const ws = wb.addWorksheet("Davomat");
  ws.columns = [{ width: 28 }, { width: 12 }, { width: 12 }, { width: 12 }, { width: 16 }];
  banner(ws, "A1:E1", `BUGUNGI DAVOMAT — ${sana}`);
  headerRow(ws.addRow(["Xodim", "Keldi", "Ketdi", "Soat", "Holat"]), HEADBLUE);

  const holatRang: Record<string, [string, string]> = {
    "Vaqtida": [OKBG, OKFG], "Kech qoldi": [WARNBG, WARNFG], "Avtomatik": [AUTOBG, AUTOFG],
  };
  let oxirgiBolim: string | undefined;
  rows.forEach((r, i) => {
    const b = r.bolim || "Bo'limsiz";
    if (b !== oxirgiBolim) { bolimHeaderRow(ws, 5, b); oxirgiBolim = b; }
    const holat = r.holat ?? "Kelmadi";
    const row = ws.addRow([r.ism, r.keldi, r.ketdi, r.soat === null ? "—" : Number(r.soat), holat]);
    row.height = 20;
    // deno-lint-ignore no-explicit-any
    row.eachCell((c: any) => { c.border = thin(); if (i % 2) c.fill = { type: "pattern", pattern: "solid", fgColor: { argb: ZEBRA } }; });
    row.getCell(1).font = { bold: true, color: { argb: NAVY } };
    [2, 3, 4].forEach((n) => { row.getCell(n).alignment = { horizontal: "center" }; });
    const [bg, fg] = holatRang[holat] ?? [BADBG, BADFG];
    row.getCell(5).fill = { type: "pattern", pattern: "solid", fgColor: { argb: bg } };
    row.getCell(5).font = { bold: true, color: { argb: fg } };
    row.getCell(5).alignment = { horizontal: "center" };
  });

  const kelgan = rows.filter((r) => r.holat && r.soat !== null).length;
  const tot = ws.addRow([`JAMI: ${kelgan}/${rows.length} keldi`, "", "", "", ""]);
  ws.mergeCells(`A${tot.number}:E${tot.number}`);
  tot.getCell(1).font = { bold: true, color: { argb: NAVY } };
  tot.getCell(1).fill = { type: "pattern", pattern: "solid", fgColor: { argb: TOTBG } };
  tot.height = 22;

  const buf = await wb.xlsx.writeBuffer();
  return new Uint8Array(buf as ArrayBuffer);
}
IMEDHRBOT_EXCEL_EOF

cat > pdf.ts <<'IMEDHRBOT_PDF_EOF'
// iMed HR bot — PDF eksport. Mavjud dashboard PNG'ni bitta sahifali PDF'ga joylaydi.
export async function pngToPdf(png: Uint8Array, widthPx: number, heightPx: number): Promise<Uint8Array> {
  const { PDFDocument } = await import("npm:pdf-lib@1.17.1");
  const pdf = await PDFDocument.create();
  const img = await pdf.embedPng(png);
  const scale = 0.75; // 96dpi (render) -> 72dpi (PDF nuqta)
  const w = widthPx * scale, h = heightPx * scale;
  const page = pdf.addPage([w, h]);
  page.drawImage(img, { x: 0, y: 0, width: w, height: h });
  return await pdf.save();
}

export interface MaoshPdfRow { ism: string; rol: string; jami_soat: number; baza: number; bonus: number; yakuniy: number; }

export async function maoshPdf(oy: string, rows: MaoshPdfRow[]): Promise<Uint8Array> {
  const { PDFDocument, StandardFonts, rgb } = await import("npm:pdf-lib@1.17.1");
  const pdf = await PDFDocument.create();
  const font = await pdf.embedFont(StandardFonts.Helvetica);
  const bold = await pdf.embedFont(StandardFonts.HelveticaBold);
  const navy = rgb(0.055, 0.165, 0.278);
  const rowH = 22, top = 780, left = 40;
  const cols = [
    { x: left, w: 200, label: "Xodim" },
    { x: left + 200, w: 100, label: "Rol" },
    { x: left + 300, w: 70, label: "Soat" },
    { x: left + 370, w: 90, label: "Baza" },
    { x: left + 460, w: 90, label: "Bonus" },
  ];

  let page = pdf.addPage([612, 842]);
  page.drawText(`OYLIK MAOSH — ${oy}`, { x: left, y: 810, size: 18, font: bold, color: navy });
  cols.forEach((c) => page.drawText(c.label, { x: c.x, y: top, size: 10, font: bold, color: navy }));

  let y = top - rowH;
  let jami = 0;
  for (const r of rows) {
    if (y < 60) { page = pdf.addPage([612, 842]); y = top; }
    jami += Number(r.yakuniy);
    page.drawText(r.ism.slice(0, 30), { x: cols[0].x, y, size: 10, font });
    page.drawText(r.rol, { x: cols[1].x, y, size: 10, font });
    page.drawText(String(r.jami_soat), { x: cols[2].x, y, size: 10, font });
    page.drawText(r.baza.toLocaleString(), { x: cols[3].x, y, size: 10, font });
    page.drawText(r.yakuniy.toLocaleString(), { x: cols[4].x, y, size: 10, font: bold });
    y -= rowH;
  }
  page.drawText(`Jami: ${jami.toLocaleString()} som`, { x: left, y: y - 10, size: 12, font: bold, color: navy });

  return await pdf.save();
}
IMEDHRBOT_PDF_EOF

echo "-- .env fayli yaratilmoqda --"
if [ ! -f .env ]; then
  cat > .env <<'IMEDHRBOT_ENV_EOF'
SUPABASE_URL=https://qechpuaeccynfvfihdrk.supabase.co
SUPABASE_SERVICE_ROLE_KEY=PASTE_SECRET_KEY_HERE
IMEDHRBOT_ENV_EOF
  echo ""
  echo "!!! DIQQAT !!!"
  echo "/opt/imed-hr-bot/.env faylini oching (masalan: nano /opt/imed-hr-bot/.env)"
  echo "va SUPABASE_SERVICE_ROLE_KEY qiymatini quyidagi joydan olib qo'ying:"
  echo "Supabase Dashboard -> Settings -> API Keys -> Secret keys -> ko'z belgisini bosib to'liq qiymatni ko'ring"
  echo "Keyin xizmatni qayta ishga tushiring: sudo systemctl restart imed-hr-bot"
  echo ""
else
  echo ".env allaqachon mavjud, o'zgartirilmadi."
fi

echo "-- systemd xizmati sozlanmoqda --"
sudo tee /etc/systemd/system/imed-hr-bot.service > /dev/null <<SYSTEMD_EOF
[Unit]
Description=iMed HR Bot (Telegram, grammY, Deno)
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/imed-hr-bot
EnvironmentFile=/opt/imed-hr-bot/.env
ExecStart=$DENO_BIN run --allow-net --allow-env --allow-read index.ts
Restart=always
RestartSec=3
User=$USER

[Install]
WantedBy=multi-user.target
SYSTEMD_EOF

sudo systemctl daemon-reload
sudo systemctl enable imed-hr-bot
sudo systemctl restart imed-hr-bot

echo "-- Caddy (avtomatik HTTPS) sozlanmoqda --"
HOST="84-247-182-49.nip.io"
sudo tee /etc/caddy/Caddyfile > /dev/null <<CADDY_EOF
$HOST {
    reverse_proxy localhost:8000
}
CADDY_EOF
sudo systemctl restart caddy

sleep 2
echo ""
echo "=========================================="
echo " O'RNATISH TUGADI"
echo " Bot manzili: https://$HOST"
echo "=========================================="
echo ""
echo "Holatni tekshirish:   sudo systemctl status imed-hr-bot"
echo "Loglarni ko'rish:     sudo journalctl -u imed-hr-bot -f"
echo "Caddy holatini ko'rish: sudo systemctl status caddy"
echo ""
echo "KEYINGI QADAM (majburiy):"
echo "1. /opt/imed-hr-bot/.env ichidagi SUPABASE_SERVICE_ROLE_KEY ni to'ldiring"
echo "2. sudo systemctl restart imed-hr-bot"
echo "3. Tekshirish: curl -i https://$HOST   (javob kelishi kerak, xatolik bo'lmasin)"
echo "4. Shundan keyin webhook'ni almashtirish uchun (O'ZINGIZNING BOT TOKENINGIZ bilan) shu buyruqni ishga tushiring:"
echo "   curl \"https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=https://$HOST\""
echo "   (<BOT_TOKEN> o'rniga haqiqiy tokenni qo'ying -- bu skriptga yozilmagan, xavfsizlik uchun)"
