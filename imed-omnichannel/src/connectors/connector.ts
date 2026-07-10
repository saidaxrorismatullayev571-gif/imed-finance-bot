import type { UnifiedMessage } from '../types/unified-message';
import type { ChannelRecord } from '../channels/repository';

/** Bitta HTTP webhook so'rovining connectorga kerakli bo'lagi. */
export interface WebhookContext {
  method: 'GET' | 'POST';
  headers: Record<string, string | undefined>;
  query: Record<string, string | undefined>;
  /** Imzo (signature) tekshiruvi uchun O'ZGARTIRILMAGAN raw body. */
  rawBody: Buffer;
  /** JSON parse qilingan body. */
  body: unknown;
  /** /webhook/:channelId route allaqachon aniqlagan kanal (agar bor bo'lsa). */
  channel?: ChannelRecord;
}

export interface VerifyResult {
  ok: boolean;
  status: number;
  /** GET subscribe uchun qaytariladigan hub.challenge. */
  challenge?: string;
  reason?: string;
}

export type OutboundKind = 'dm' | 'comment';

export interface OutboundMessage {
  channel: ChannelRecord;
  kind: OutboundKind;
  /** DM uchun oluvchi id, comment uchun comment id. */
  to: string;
  text: string;
}

/**
 * Har bir kanal integratsiyasi shu interfeysni bajaradi.
 *  - verify: webhook'ni tasdiqlash (GET challenge yoki POST signature)
 *  - parse:  kiruvchi payloadni UnifiedMessage[] ga o'girish
 *  - send:   chiquvchi xabarni yuborish
 */
export interface Connector {
  readonly type: string;
  verify(ctx: WebhookContext): VerifyResult | Promise<VerifyResult>;
  parse(ctx: WebhookContext): Promise<UnifiedMessage[]>;
  send(msg: OutboundMessage): Promise<void>;
}
