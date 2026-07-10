-- 0002: indekslar (channel resolution tezligi + idempotentlik)

-- Instagram business account id bo'yicha tezkor qidiruv
CREATE INDEX idx_channels_ig_id
  ON channels ((config->>'ig_id'))
  WHERE channel_type = 'instagram';

CREATE INDEX idx_channels_active
  ON channels (channel_type)
  WHERE is_active;

-- Idempotentlik: bitta kanalda bir xil external_id ikki marta yozilmasin.
-- (NULL external_id'lar bir-biridan farqli hisoblanadi — muammosiz.)
CREATE UNIQUE INDEX uq_messages_channel_external
  ON messages (channel_id, external_id);
