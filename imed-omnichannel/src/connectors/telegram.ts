import type {
  Connector,
  WebhookContext,
  VerifyResult,
  OutboundMessage,
} from './connector';
import type { UnifiedMessage } from '../types/unified-message';

/**
 * Telegram connector — mavjud arxitektura namunasi. Telegram har bir kanal
 * uchun ALOHIDA callback URL ishlatadi, shuning uchun u /webhook/:channelId
 * pattern orqali ishlaydi (kanal route tomonidan aniqlanadi).
 */
export class TelegramConnector implements Connector {
  readonly type = 'telegram';

  verify(ctx: WebhookContext): VerifyResult {
    // Ixtiyoriy: X-Telegram-Bot-Api-Secret-Token header'ini tekshirish mumkin.
    const expected = ctx.channel?.config?.secret_token as string | undefined;
    if (expected) {
      const got = ctx.headers['x-telegram-bot-api-secret-token'];
      if (got !== expected) {
        return { ok: false, status: 401, reason: 'secret_token mos kelmadi' };
      }
    }
    return { ok: true, status: 200 };
  }

  async parse(ctx: WebhookContext): Promise<UnifiedMessage[]> {
    const channel = ctx.channel;
    if (!channel) return [];
    const update = ctx.body as any;
    const m = update?.message;
    if (!m) return [];
    const senderId = String(m.from?.id ?? m.chat?.id ?? '');
    if (!senderId) return [];
    const chatId = String(m.chat?.id ?? senderId);
    return [
      {
        channelType: 'telegram',
        tenantId: channel.tenantId,
        channelId: channel.id,
        kind: 'dm',
        externalMessageId: `${chatId}:${m.message_id}`,
        conversationId: chatId,
        senderId,
        senderName: m.from?.username,
        text: m.text,
        attachments: [],
        timestamp: m.date ? Number(m.date) * 1000 : Date.now(),
        replyTo: chatId,
        raw: update,
      },
    ];
  }

  async send(msg: OutboundMessage): Promise<void> {
    const token = msg.channel.config.bot_token as string | undefined;
    if (!token) throw new Error(`channel ${msg.channel.id}: bot_token yo'q`);
    const res = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ chat_id: msg.to, text: msg.text }),
    });
    if (!res.ok) {
      throw new Error(`Telegram sendMessage xatosi: ${res.status}`);
    }
  }
}
