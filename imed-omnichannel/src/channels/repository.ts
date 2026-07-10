import type { Pool } from 'pg';
import type { UnifiedChannelType, UnifiedMessage } from '../types/unified-message';

/** channels jadvalidagi bitta kanal yozuvi. */
export interface ChannelRecord {
  id: string;
  tenantId: string;
  channelType: UnifiedChannelType;
  name: string;
  /** Kanalga xos sozlamalar: page_id, ig_id, page_access_token, bot_token, ... */
  config: Record<string, any>;
  isActive: boolean;
}

export class ChannelRepository {
  constructor(private readonly pool: Pool) {}

  /** UUID bo'yicha kanalni topish (/webhook/:channelId uchun). */
  async getById(id: string): Promise<ChannelRecord | null> {
    const { rows } = await this.pool.query(
      `SELECT id, tenant_id, channel_type, name, config, is_active
         FROM channels
        WHERE id = $1`,
      [id],
    );
    return rows[0] ? this.map(rows[0]) : null;
  }

  /**
   * Meta channel resolution: payloaddagi entry[].id bo'yicha kanalni topish.
   * Instagram uchun entry.id = IG business account id (config.ig_id),
   * Facebook uchun entry.id = Page id (config.page_id).
   */
  async resolveMeta(
    entryId: string,
    platform: 'instagram' | 'facebook',
  ): Promise<ChannelRecord | null> {
    const key = platform === 'instagram' ? 'ig_id' : 'page_id';
    const { rows } = await this.pool.query(
      `SELECT id, tenant_id, channel_type, name, config, is_active
         FROM channels
        WHERE channel_type = $1
          AND config->>$2 = $3
          AND is_active = true
        LIMIT 1`,
      [platform, key, entryId],
    );
    return rows[0] ? this.map(rows[0]) : null;
  }

  /** Kiruvchi xabarni jurnalga yozish (external_id bo'yicha idempotent). */
  async saveInbound(msg: UnifiedMessage): Promise<void> {
    await this.pool.query(
      `INSERT INTO messages
         (tenant_id, channel_id, direction, kind, external_id, sender_id, text, raw)
       VALUES ($1, $2, 'inbound', $3, $4, $5, $6, $7)
       ON CONFLICT (channel_id, external_id) DO NOTHING`,
      [
        msg.tenantId,
        msg.channelId,
        msg.kind,
        msg.externalMessageId,
        msg.senderId,
        msg.text ?? null,
        JSON.stringify(msg.raw ?? null),
      ],
    );
  }

  private map(row: any): ChannelRecord {
    return {
      id: row.id,
      tenantId: row.tenant_id,
      channelType: row.channel_type,
      name: row.name,
      config: row.config ?? {},
      isActive: row.is_active,
    };
  }
}
