# iMed Omnichannel

Ko'p kanalli xabar platformasi — **Telegram, Instagram, Facebook** xabar/izohlarini
yagona `UnifiedMessage` formatida qabul qiladi va javob yuboradi.

## Arxitektura

| Qatlam | Texnologiya |
|---|---|
| Server | Node.js 22 + Fastify + TypeScript |
| Baza | PostgreSQL 16 (`pg`) |
| Yadro | `Connector` interfeysi (`verify` / `parse` / `send`) + `ConnectorRegistry` |

**G'oya:** har bir integratsiya `Connector` ni bajaradi. Kiruvchi webhook →
`verify` → `parse` → `UnifiedMessage[]` → `dispatcher`. Chiquvchi → `send`.

```
src/
├── env.ts                     # env o'qish + validatsiya
├── app.ts                     # Fastify, raw-body parser, registry, route'lar
├── index.ts                   # kirish nuqtasi
├── dispatcher.ts              # UnifiedMessage -> jurnal
├── types/unified-message.ts   # UnifiedMessage
├── channels/repository.ts     # channels + messages (channel resolution)
├── connectors/
│   ├── connector.ts           # Connector interfeysi
│   ├── registry.ts            # ConnectorRegistry
│   ├── telegram.ts            # Telegram (per-channel URL namunasi)
│   └── meta/
│       ├── index.ts           # MetaConnector (IG + FB)
│       ├── signature.ts       # X-Hub-Signature-256 (HMAC-SHA256)
│       ├── normalizer.ts      # entry[] -> UnifiedMessage (DM + comment)
│       ├── graph.ts           # Graph API send
│       └── rate-limiter.ts    # IG 200 xabar/soat navbati
├── routes/
│   ├── webhook.ts             # GET/POST /webhook/:channelId
│   ├── meta-webhook.ts        # GET/POST /webhook/meta
│   └── context.ts             # Fastify req -> WebhookContext
└── db/
    ├── migrate.ts             # migratsiya ijrochisi
    └── migrations/
        ├── 0001_init.sql
        ├── 0002_indexes.sql
        └── 0003_add_facebook_channel_type.sql
```

## Webhook URL'lari

- **Telegram** (va har kanal alohida URL ishlatadigan integratsiyalar):
  `POST /webhook/:channelId` — kanal UUID orqali topiladi.
- **Meta (Instagram + Facebook)** — BITTA callback URL:
  - `GET  /webhook/meta` — `hub.verify_token === META_VERIFY_TOKEN` bo'lsa `hub.challenge` qaytaradi.
  - `POST /webhook/meta` — `X-Hub-Signature-256` (raw body, `META_APP_SECRET`) tekshiriladi.
    Kanal payloaddagi `entry[].id` (IG business id / FB page id) bo'yicha aniqlanadi.

## Kanal sozlamalari (channels.config)

| channel_type | config kalitlari |
|---|---|
| `instagram` | `ig_id`, `page_access_token` |
| `facebook`  | `page_id`, `page_access_token` |
| `telegram`  | `bot_token`, `secret_token?` |

## Ishga tushirish

```bash
pnpm install
cp .env.example .env      # DATABASE_URL, META_APP_SECRET, META_VERIFY_TOKEN kiriting
pnpm migrate              # 0001 -> 0002 -> 0003
pnpm dev                  # yoki: pnpm build && pnpm start
```

## Buyruqlar

| Buyruq | Vazifa |
|---|---|
| `pnpm typecheck` | TypeScript tekshiruvi (emit yo'q) |
| `pnpm build` | `dist/` ga kompilyatsiya |
| `pnpm migrate` | migratsiyalarni qo'llash |
| `pnpm dev` | hot-reload server |
