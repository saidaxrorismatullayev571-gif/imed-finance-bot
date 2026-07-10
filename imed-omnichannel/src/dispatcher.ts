import type { UnifiedMessage } from './types/unified-message';
import type { ChannelRepository } from './channels/repository';

/** Normallashtirilgan xabarlar bilan nima qilishni belgilaydigan funksiya. */
export type MessageDispatcher = (messages: UnifiedMessage[]) => Promise<void>;

/**
 * Oddiy dispatcher: har bir kiruvchi xabarni jurnalga yozadi va log qiladi.
 * Keyingi fazalarda bu yerga avto-javob / operatorga uzatish qo'shiladi.
 */
export function createDispatcher(
  channels: ChannelRepository,
  log: (msg: string) => void,
): MessageDispatcher {
  return async (messages) => {
    for (const m of messages) {
      await channels.saveInbound(m);
      log(`[${m.channelType}] ${m.kind} <- ${m.senderId}: ${m.text ?? '(matnsiz)'}`);
    }
  };
}
