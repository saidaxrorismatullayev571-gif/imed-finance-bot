-- 0003: Facebook (Messenger + feed comment) qo'llab-quvvatlash

-- channel_type enum'iga 'facebook' qiymatini qo'shamiz.
-- Eslatma (PG 16): ADD VALUE tranzaksiya ichida bajarilishi mumkin, faqat
-- yangi qiymat aynan shu tranzaksiyada ISHLATILMASA. Quyidagi indeks enum
-- qiymatiga tayanmaydi, shuning uchun muammosiz.
ALTER TYPE channel_type ADD VALUE IF NOT EXISTS 'facebook';

-- Facebook Page id bo'yicha channel resolution indeksi
CREATE INDEX IF NOT EXISTS idx_channels_page_id
  ON channels ((config->>'page_id'));
