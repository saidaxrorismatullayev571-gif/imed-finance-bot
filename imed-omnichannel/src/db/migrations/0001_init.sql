-- 0001: boshlang'ich sxema (tenants, channels, messages)

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE tenants (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name       text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Boshlang'ich kanal turlari. 'facebook' keyinroq 0003 da qo'shiladi.
CREATE TYPE channel_type AS ENUM ('telegram', 'instagram');

CREATE TABLE channels (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id    uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  channel_type channel_type NOT NULL,
  name         text NOT NULL,
  -- Kanalga xos sozlamalar: page_id, ig_id, page_access_token, bot_token, ...
  config       jsonb NOT NULL DEFAULT '{}'::jsonb,
  is_active    boolean NOT NULL DEFAULT true,
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE messages (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  channel_id  uuid NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
  direction   text NOT NULL CHECK (direction IN ('inbound', 'outbound')),
  kind        text NOT NULL CHECK (kind IN ('dm', 'comment')),
  external_id text,
  sender_id   text,
  text        text,
  raw         jsonb,
  created_at  timestamptz NOT NULL DEFAULT now()
);
