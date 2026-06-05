-- ============================================================
-- iMed Finance Bot — Initial Schema (Faza 0)
-- PostgreSQL 14+
--
-- ASOSIY PRINSIP:
--   `transactions` jadvali — yagona, o'zgarmas (immutable) jurnal.
--   BARCHA balanslar HISOBLAB chiqariladi (hech qachon saqlanmaydi),
--   shuning uchun balans hech qachon "adashmaydi" / yo'qolmaydi.
-- ============================================================

BEGIN;

-- ----------------- ENUM TIPLAR -----------------
CREATE TYPE user_role      AS ENUM ('admin', 'manager', 'viewer');
CREATE TYPE currency_code  AS ENUM ('UZS', 'USD');

CREATE TYPE txn_kind AS ENUM (
    'opening',         -- boshlang'ich balans
    'income',          -- daromad (kirim)
    'expense',         -- xarajat (chiqim)
    'transfer_out',    -- transfer: chiqish oyog'i
    'transfer_in',     -- transfer: kirish oyog'i
    'debt_out',        -- qarz BERDIK (kassadan chiqdi)
    'debt_in',         -- qarz OLDIK / bizga qaytdi (kassaga kirdi)
    'debt_repay_out'   -- biz olgan qarzni QAYTARDIK (kassadan chiqdi)
);

CREATE TYPE debt_direction AS ENUM ('lent', 'borrowed');  -- berdim / oldim
CREATE TYPE debt_status    AS ENUM ('open', 'partial', 'paid', 'overdue', 'written_off');

-- ----------------- MASTER / SPRAVOCHNIK -----------------
CREATE TABLE users (
    id           BIGSERIAL PRIMARY KEY,
    telegram_id  BIGINT UNIQUE NOT NULL,
    full_name    TEXT NOT NULL,
    phone        TEXT,
    role         user_role NOT NULL DEFAULT 'viewer',
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE wallets (                         -- kassalar
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    currency    currency_code NOT NULL,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (name, currency)
);

CREATE TABLE funds (                           -- fondlar
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    description TEXT,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE income_sources (                  -- daromad manbalari
    id        BIGSERIAL PRIMARY KEY,
    name      TEXT NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE expense_categories (              -- xarajat kategoriyalari (ierarxik)
    id         BIGSERIAL PRIMARY KEY,
    name       TEXT NOT NULL,
    parent_id  BIGINT REFERENCES expense_categories(id) ON DELETE SET NULL,
    is_active  BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (name, parent_id)
);

-- ----------------- VALYUTA KURSLARI (CBU monitoring) -----------------
CREATE TABLE exchange_rates (
    id         BIGSERIAL PRIMARY KEY,
    currency   currency_code NOT NULL,
    rate_uzs   NUMERIC(18,6) NOT NULL CHECK (rate_uzs > 0),
    source     TEXT NOT NULL DEFAULT 'CBU',
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_fx_currency_time ON exchange_rates (currency, fetched_at DESC);

-- ----------------- QARZLAR -----------------
CREATE TABLE debts (
    id                 BIGSERIAL PRIMARY KEY,
    direction          debt_direction NOT NULL,
    counterparty_name  TEXT NOT NULL,
    counterparty_phone TEXT,
    principal          NUMERIC(18,2) NOT NULL CHECK (principal > 0),
    currency           currency_code NOT NULL,
    wallet_id          BIGINT NOT NULL REFERENCES wallets(id),
    fund_id            BIGINT REFERENCES funds(id),
    issued_at          DATE NOT NULL DEFAULT CURRENT_DATE,
    due_date           DATE,
    status             debt_status NOT NULL DEFAULT 'open',
    note               TEXT,
    created_by         BIGINT NOT NULL REFERENCES users(id),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_debts_status ON debts (status);
CREATE INDEX idx_debts_due    ON debts (due_date)
    WHERE status IN ('open','partial','overdue');

-- ----------------- JURNAL (LEDGER) -----------------
CREATE TABLE transactions (
    id                BIGSERIAL PRIMARY KEY,
    kind              txn_kind NOT NULL,
    wallet_id         BIGINT NOT NULL REFERENCES wallets(id),
    fund_id           BIGINT REFERENCES funds(id),
    amount            NUMERIC(18,2) NOT NULL CHECK (amount > 0),   -- doim musbat
    currency          currency_code NOT NULL,
    fx_rate           NUMERIC(18,6) NOT NULL DEFAULT 1 CHECK (fx_rate > 0),  -- UZS ga
    amount_uzs        NUMERIC(18,2) NOT NULL CHECK (amount_uzs > 0),
    -- balans matematikasi uchun ishorali summa (generated):
    signed_uzs        NUMERIC(18,2) GENERATED ALWAYS AS (
        CASE WHEN kind IN ('opening','income','transfer_in','debt_in')
             THEN amount_uzs ELSE -amount_uzs END
    ) STORED,
    source_id         BIGINT REFERENCES income_sources(id),
    category_id       BIGINT REFERENCES expense_categories(id),
    debt_id           BIGINT REFERENCES debts(id),
    transfer_group_id UUID,                     -- transferning ikki oyog'ini bog'laydi
    description       TEXT,
    occurred_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by        BIGINT NOT NULL REFERENCES users(id),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_txn_wallet   ON transactions (wallet_id);
CREATE INDEX idx_txn_fund     ON transactions (fund_id);
CREATE INDEX idx_txn_kind     ON transactions (kind);
CREATE INDEX idx_txn_occurred ON transactions (occurred_at);
CREATE INDEX idx_txn_debt     ON transactions (debt_id);

CREATE TABLE debt_payments (
    id             BIGSERIAL PRIMARY KEY,
    debt_id        BIGINT NOT NULL REFERENCES debts(id) ON DELETE CASCADE,
    amount         NUMERIC(18,2) NOT NULL CHECK (amount > 0),
    currency       currency_code NOT NULL,
    fx_rate        NUMERIC(18,6) NOT NULL DEFAULT 1,
    paid_at        DATE NOT NULL DEFAULT CURRENT_DATE,
    transaction_id BIGINT REFERENCES transactions(id),
    created_by     BIGINT NOT NULL REFERENCES users(id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_debtpay_debt ON debt_payments (debt_id);

CREATE TABLE debt_reminders (
    id         BIGSERIAL PRIMARY KEY,
    debt_id    BIGINT NOT NULL REFERENCES debts(id) ON DELETE CASCADE,
    remind_at  TIMESTAMPTZ NOT NULL,
    is_sent    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_reminder_due ON debt_reminders (remind_at) WHERE is_sent = FALSE;

-- ----------------- AUDIT LOG -----------------
CREATE TABLE audit_logs (
    id           BIGSERIAL PRIMARY KEY,
    actor_id     BIGINT REFERENCES users(id),
    action       TEXT NOT NULL,        -- INSERT / UPDATE / DELETE
    entity_type  TEXT NOT NULL,
    entity_id    TEXT,
    before_data  JSONB,
    after_data   JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_entity ON audit_logs (entity_type, entity_id);
CREATE INDEX idx_audit_time   ON audit_logs (created_at DESC);

-- ----------------- HISOBLANADIGAN BALANS VIEW'LARI -----------------
-- Kassa balansi
CREATE VIEW v_wallet_balances AS
SELECT w.id AS wallet_id, w.name, w.currency,
       COALESCE(SUM(t.signed_uzs), 0) AS balance_uzs
FROM wallets w
LEFT JOIN transactions t ON t.wallet_id = w.id
GROUP BY w.id, w.name, w.currency;

-- Fond balansi
CREATE VIEW v_fund_balances AS
SELECT f.id AS fund_id, f.name,
       COALESCE(SUM(t.signed_uzs), 0) AS balance_uzs
FROM funds f
LEFT JOIN transactions t ON t.fund_id = f.id
GROUP BY f.id, f.name;

-- Fond × Kassa kesimi
CREATE VIEW v_fund_wallet_balances AS
SELECT t.fund_id, t.wallet_id,
       COALESCE(SUM(t.signed_uzs), 0) AS balance_uzs
FROM transactions t
WHERE t.fund_id IS NOT NULL
GROUP BY t.fund_id, t.wallet_id;

-- Qarz qoldig'i
CREATE VIEW v_debt_outstanding AS
SELECT d.id AS debt_id, d.direction, d.counterparty_name, d.currency,
       d.principal,
       COALESCE(SUM(p.amount), 0)               AS paid,
       d.principal - COALESCE(SUM(p.amount), 0) AS remaining,
       d.due_date, d.status
FROM debts d
LEFT JOIN debt_payments p ON p.debt_id = d.id
GROUP BY d.id;

COMMIT;
