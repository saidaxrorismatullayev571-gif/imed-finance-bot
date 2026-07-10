import type { FastifyInstance } from 'fastify';
import type { ConnectorRegistry } from '../connectors/registry';
import type { ChannelRepository } from '../channels/repository';
import type { MessageDispatcher } from '../dispatcher';
import { buildContext } from './context';

/**
 * Umumiy per-channel webhook: /webhook/:channelId
 * Kanal UUID orqali topiladi, channel_type bo'yicha connector tanlanadi.
 * (Telegram kabi har kanal alohida URL ishlatadigan integratsiyalar uchun.)
 */
export function registerChannelWebhook(
  app: FastifyInstance,
  registry: ConnectorRegistry,
  channels: ChannelRepository,
  dispatch: MessageDispatcher,
): void {
  app.get('/webhook/:channelId', async (req, reply) => {
    const { channelId } = req.params as { channelId: string };
    const channel = await channels.getById(channelId);
    if (!channel) return reply.status(404).send('kanal topilmadi');
    const connector = registry.get(channel.channelType);
    if (!connector) return reply.status(400).send('connector yo‘q');

    const ctx = buildContext(req, 'GET');
    ctx.channel = channel;
    const v = await connector.verify(ctx);
    if (v.ok) return reply.status(200).send(v.challenge ?? 'ok');
    return reply.status(v.status).send(v.reason ?? 'forbidden');
  });

  app.post('/webhook/:channelId', async (req, reply) => {
    const { channelId } = req.params as { channelId: string };
    const channel = await channels.getById(channelId);
    if (!channel) return reply.status(404).send('kanal topilmadi');
    const connector = registry.get(channel.channelType);
    if (!connector) return reply.status(400).send('connector yo‘q');

    const ctx = buildContext(req, 'POST');
    ctx.channel = channel;
    const v = await connector.verify(ctx);
    if (!v.ok) return reply.status(v.status).send(v.reason ?? 'unauthorized');

    reply.status(200).send('ok');
    try {
      const messages = await connector.parse(ctx);
      await dispatch(messages);
    } catch (err) {
      req.log.error({ err }, 'webhook parse/dispatch xatosi');
    }
  });
}
