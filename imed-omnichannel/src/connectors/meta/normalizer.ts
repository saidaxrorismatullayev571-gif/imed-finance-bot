import type { ChannelRecord } from '../../channels/repository';
import type { UnifiedMessage, UnifiedAttachment } from '../../types/unified-message';

export type MetaPlatform = 'instagram' | 'facebook';

/**
 * Bitta entry'ni UnifiedMessage[] ga o'giradi:
 *  - entry.messaging[]  -> DM (Instagram DM / FB Messenger)
 *  - entry.changes[]    -> comment (IG comment / FB feed comment)
 */
export function normalizeEntry(
  entry: any,
  platform: MetaPlatform,
  channel: ChannelRecord,
): UnifiedMessage[] {
  const out: UnifiedMessage[] = [];

  if (Array.isArray(entry?.messaging)) {
    for (const ev of entry.messaging) {
      const um = normalizeMessagingEvent(ev, channel);
      if (um) out.push(um);
    }
  }

  if (Array.isArray(entry?.changes)) {
    for (const ch of entry.changes) {
      const um = normalizeChange(ch, platform, channel);
      if (um) out.push(um);
    }
  }

  return out;
}

/** entry.messaging[] elementi -> DM. */
function normalizeMessagingEvent(
  ev: any,
  channel: ChannelRecord,
): UnifiedMessage | null {
  const message = ev?.message;
  if (!message) return null; // delivery/read/postback — hozircha o'tkazib yuboramiz
  if (message.is_echo) return null; // o'zimiz yuborgan xabar aks-sadosi

  const senderId = ev?.sender?.id ? String(ev.sender.id) : '';
  if (!senderId) return null;

  return {
    channelType: channel.channelType,
    tenantId: channel.tenantId,
    channelId: channel.id,
    kind: 'dm',
    externalMessageId: String(message.mid ?? `${senderId}:${ev.timestamp ?? ''}`),
    conversationId: senderId,
    senderId,
    text: typeof message.text === 'string' ? message.text : undefined,
    attachments: extractAttachments(message.attachments),
    timestamp: Number(ev.timestamp) || Date.now(),
    replyTo: senderId, // DM javob -> foydalanuvchi id
    raw: ev,
  };
}

/** entry.changes[] elementi -> comment. */
function normalizeChange(
  ch: any,
  platform: MetaPlatform,
  channel: ChannelRecord,
): UnifiedMessage | null {
  const value = ch?.value ?? {};

  if (platform === 'instagram') {
    // IG: field=comments
    if (ch?.field !== 'comments') return null;
    const commentId = value.id ? String(value.id) : '';
    if (!commentId) return null;
    return {
      channelType: channel.channelType,
      tenantId: channel.tenantId,
      channelId: channel.id,
      kind: 'comment',
      externalMessageId: commentId,
      conversationId: value.media?.id ? String(value.media.id) : commentId,
      senderId: value.from?.id ? String(value.from.id) : 'unknown',
      senderName: value.from?.username,
      text: typeof value.text === 'string' ? value.text : undefined,
      attachments: [],
      timestamp: Date.now(),
      replyTo: commentId, // IG comment javob -> comment id
      raw: ch,
    };
  }

  // FB: field=feed, item=comment (faqat yangi qo'shilgan izohlar)
  if (ch?.field !== 'feed') return null;
  if (value.item !== 'comment') return null;
  if (value.verb && value.verb !== 'add') return null;
  const commentId = value.comment_id ? String(value.comment_id) : '';
  if (!commentId) return null;
  return {
    channelType: channel.channelType,
    tenantId: channel.tenantId,
    channelId: channel.id,
    kind: 'comment',
    externalMessageId: commentId,
    conversationId: value.post_id ? String(value.post_id) : commentId,
    senderId: value.from?.id ? String(value.from.id) : 'unknown',
    senderName: value.from?.name,
    text: typeof value.message === 'string' ? value.message : undefined,
    attachments: [],
    timestamp: value.created_time ? Number(value.created_time) * 1000 : Date.now(),
    replyTo: commentId, // FB comment javob -> comment id
    raw: ch,
  };
}

function extractAttachments(attachments: any): UnifiedAttachment[] {
  if (!Array.isArray(attachments)) return [];
  const out: UnifiedAttachment[] = [];
  for (const a of attachments) {
    const url = a?.payload?.url;
    if (typeof url === 'string') {
      out.push({ type: typeof a.type === 'string' ? a.type : 'other', url });
    }
  }
  return out;
}
