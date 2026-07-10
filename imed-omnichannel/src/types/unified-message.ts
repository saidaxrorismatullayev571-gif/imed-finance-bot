/**
 * UnifiedMessage — barcha kanallar (Telegram, Instagram, Facebook) uchun
 * yagona, normallashtirilgan xabar formati. Har bir connector kiruvchi
 * webhook'ni shu turga o'giradi.
 */

export type UnifiedChannelType = 'telegram' | 'instagram' | 'facebook';

/** Xabar turi: shaxsiy xabar (DM) yoki post ostidagi izoh (comment). */
export type UnifiedMessageKind = 'dm' | 'comment';

export interface UnifiedAttachment {
  type: string; // image | video | audio | file | ...
  url: string;
}

export interface UnifiedMessage {
  channelType: UnifiedChannelType;
  /** Bizning ichki tenant (mijoz) id'si. */
  tenantId: string;
  /** Bizning ichki channels.id (UUID). */
  channelId: string;
  kind: UnifiedMessageKind;
  /** Provayderdagi xabar/izoh id'si (idempotentlik uchun). */
  externalMessageId: string;
  /** Suhbat id'si: DM uchun foydalanuvchi id, comment uchun media/post id. */
  conversationId: string;
  /** Jo'natuvchining provayderdagi id'si. */
  senderId: string;
  senderName?: string;
  text?: string;
  attachments: UnifiedAttachment[];
  /** Unix ms. */
  timestamp: number;
  /** Javob manzili: DM uchun foydalanuvchi id, comment uchun comment id. */
  replyTo: string;
  /** Asl payload bo'lagi (audit/debug uchun). */
  raw: unknown;
}
