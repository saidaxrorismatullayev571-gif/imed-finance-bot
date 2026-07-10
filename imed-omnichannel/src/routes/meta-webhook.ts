import type { FastifyInstance } from 'fastify';
import type { MetaConnector } from '../connectors/meta';
import type { MessageDispatcher } from '../dispatcher';
import { buildContext } from './context';

/**
 * Meta uchun ALOHIDA route: /webhook/meta (per-channel EMAS).
 * Meta barcha IG/FB hodisalari uchun bitta callback URL ishlatadi;
 * kanal payloaddagi entry[].id orqali connector ichida aniqlanadi.
 */
export function registerMetaWebhook(
  app: FastifyInstance,
  meta: MetaConnector,
  dispatch: MessageDispatcher,
): void {
  // GET: webhook subscribe tasdiqlash
  app.get('/webhook/meta', async (req, reply) => {
    const ctx = buildContext(req, 'GET');
    const result = await meta.verify(ctx);
    if (result.ok) {
      // Meta hub.challenge'ni AYNAN qaytarishni kutadi
      return reply.status(200).send(result.challenge ?? '');
    }
    return reply.status(result.status).send(result.reason ?? 'forbidden');
  });

  // POST: hodisalar (imzo tekshiruvi bilan)
  app.post('/webhook/meta', async (req, reply) => {
    const ctx = buildContext(req, 'POST');
    const v = await meta.verify(ctx);
    if (!v.ok) return reply.status(v.status).send(v.reason ?? 'unauthorized');

    // Metaga tez 200 qaytarish kerak, aks holda u qayta yuboradi
    reply.status(200).send('EVENT_RECEIVED');
    try {
      const messages = await meta.parse(ctx);
      await dispatch(messages);
    } catch (err) {
      req.log.error({ err }, 'meta webhook parse/dispatch xatosi');
    }
  });
}
