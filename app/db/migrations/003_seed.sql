-- ============================================================
-- Boshlang'ich ma'lumotlar (seed) — SHAXSIY moliya konteksti.
-- Bularni keyin bot orqali tahrirlash/qo'shish mumkin.
-- ============================================================

BEGIN;

-- Fondlar (shaxsiy maqsadlar bo'yicha pulni ajratish)
INSERT INTO funds (name, description) VALUES
    ('Jamg''arma',          'Uzoq muddatli jamg''arma'),
    ('Kundalik xarajatlar', 'Kunlik ehtiyojlar uchun'),
    ('Zaxira',              'Favqulodda holatlar uchun zaxira'),
    ('Investitsiya',        'Investitsiyaga ajratilgan mablag''')
ON CONFLICT (name) DO NOTHING;

-- Kassalar
INSERT INTO wallets (name, currency) VALUES
    ('Naqd UZS', 'UZS'),
    ('Karta UZS', 'UZS'),
    ('Naqd USD', 'USD')
ON CONFLICT (name, currency) DO NOTHING;

-- Daromad manbalari
INSERT INTO income_sources (name) VALUES
    ('Ish haqi'),
    ('Qo''shimcha daromad'),
    ('Sovg''a'),
    ('Investitsiya daromadi'),
    ('Boshqa')
ON CONFLICT (name) DO NOTHING;

-- Xarajat kategoriyalari
INSERT INTO expense_categories (name) VALUES
    ('Oziq-ovqat'),
    ('Transport'),
    ('Uy-joy'),
    ('Sog''liq'),
    ('Ta''lim'),
    ('Kiyim'),
    ('Ko''ngilochar'),
    ('Boshqa')
ON CONFLICT (name, parent_id) DO NOTHING;

COMMIT;
