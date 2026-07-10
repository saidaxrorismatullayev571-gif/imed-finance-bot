import { env } from '../../env';
import type {
  Connector,
  WebhookContext,
  VerifyResult,
  OutboundMessage,
} from '../connector';
import type { UnifiedMessage } from '../../types/unified-message';
import type { ChannelRepository } from '../../channels/repository';
import { verifySignature } from './signature';
import { normalizeEntry, type MetaPlatform } from './normalizer';
import { graphPost } from './graph';
import { HourlyRateLimiter } from './rate-limiter';

/**
 * MetaConnector — Instagram + Facebook uchun yagona connector.
 * Meta BITTA callback URL (/webhook/meta) ishlatadi, shuning uchun kanal
 * per-so'rov emas, balki payloaddagi entry[].id bo'yicha aniqlanadi.
 */
export class MetaConnector implements Connector {
  readonly type = 'meta';

  /** Instagram DM: 200 xabar/soat himoyasi. */
  private readonly igLimiter = new HourlyRateLimiter(200);

  constructor(private readonly channels: ChannelRepository) {}

  verify(ctx: WebhookContext): VerifyResult {
    // GET: webhook subscribe tasdiqlash (hub.challenge)
    if (ctx.method === 'GET') {
      const mode = ctx.query['hub.mode'];
      const token = ctx.query['hub.verify_token'];
      const challenge = ctx.query['hub.challenge'];
      if (mode === 'subscribe' && token === env.META_VERIFY_TOKEN) {
        return { ok: true, status: 200, challenge: challenge ?? '' };
      }
      return { ok: false, status: 403, reason: 'verify_token mos kelmadi' };
    }

    // POST: X-Hub-Signature-256 (raw body ustidan HMAC-SHA256)
    const sig = ctx.headers['x-hub-signature-256'];
    if (!verifySignature(env.META_APP_SECRET, ctx.rawBody, sig)) {
      return { ok: false, status: 401, reason: 'imzo (signature) noto‘g‘ri' };
    }
    return { ok: true, status: 200 };
  }

  async parse(ctx: WebhookContext): Promise<UnifiedMessage[]> {
    const body = ctx.body as any;
    if (!body || !Array.isArray(body.entry)) return [];

    // object: 'instagram' -> IG, 'page' -> Facebook
    const platform: MetaPlatform = body.object === 'instagram' ? 'instagram' : 'facebook';

    const out: UnifiedMessage[] = [];
    for (const entry of body.entry) {
      const entryId = entry?.id ? String(entry.id) : '';
      if (!entryId) continue;
      const channel = await this.channels.resolveMeta(entryId, platform);
      if (!channel) continue; // notanish IG/Page id — o'tkazib yuboramiz
      out.push(...normalizeEntry(entry, platform, channel));
    }
    return out;
  }

  async send(msg: OutboundMessage): Promise<void> {
    const token = msg.channel.config.page_access_token as string | undefined;
    if (!token) {
      throw new Error(`channel ${msg.channel.id}: page_access_token yo'q`);
    }
    const isInstagram = msg.channel.channelType === 'instagram';

    const doSend = async (): Promise<void> => {
      let path: string;
      let payload: unknown;
      if (msg.kind === 'dm') {
        // Messenger / IG DM
        path = 'me/messages';
        payload = {
          recipient: { id: msg.to },
          message: { text: msg.text },
          messaging_type: 'RESPONSE',
        };
      } else {
        // Comment reply: IG -> /{comment-id}/replies, FB -> /{comment-id}/comments
        path = isInstagram ? `${msg.to}/replies` : `${msg.to}/comments`;
        payload = { message: msg.text };
      }
      const res = await graphPost(path, token, payload);
      if (!res.ok) {
        throw new Error(`Graph API xatosi ${res.status}: ${JSON.stringify(res.body)}`);
      }
    };

    // Instagram uchun rate-limit navbati orqali
    if (isInstagram) {
      await this.igLimiter.schedule(doSend);
    } else {
      await doSend();
    }
  }
}
