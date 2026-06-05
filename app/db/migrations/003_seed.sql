-- ============================================================
-- Boshlang'ich ma'lumotlar (seed) — iMed kontekstidan olingan standart sozlamalar.
-- Bularni keyin bot orqali tahrirlash/qo'shish mumkin.
-- ============================================================

BEGIN;

-- Fondlar
INSERT INTO funds (name, description) VALUES
    ('Asosiy',   'Asosiy operatsion fond'),
    ('Rezerv',   'Zaxira fondi'),
    ('Dividend', 'Ulushdorlarga taqsimot fondi')
ON CONFLICT (name) DO NOTHING;

-- Kassalar
INSERT INTO wallets (name, currency) VALUES
    ('Naqd UZS', 'UZS'),
    ('Karta UZS', 'UZS'),
    ('Naqd USD', 'USD')
ON CONFLICT (name, currency) DO NOTHING;

-- Daromad manbalari
INSERT INTO income_sources (name) VALUES
    ('Onlayn kurs'),
    ('Offline kurs'),
    ('Kitob'),
    ('Obuna'),
    ('Boshqa')
ON CONFLICT (name) DO NOTHING;

-- Xarajat kategoriyalari (asosiy)
INSERT INTO expense_categories (name) VALUES
    ('Ish haqi'),
    ('Marketing'),
    ('Ijara'),
    ('Kontent ishlab chiqarish'),
    ('Texnik xarajatlar'),
    ('Soliq'),
    ('Boshqa')
ON CONFLICT (name, parent_id) DO NOTHING;

COMMIT;
