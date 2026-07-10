import Fastify, { type FastifyInstance } from 'fastify';
import type { Pool } from 'pg';
import { assertMetaEnv } from './env';
import { ChannelRepository } from './channels/repository';
import { ConnectorRegistry } from './connectors/registry';
import { TelegramConnector } from './connectors/telegram';
import { MetaConnector } from './connectors/meta';
import { registerChannelWebhook } from './routes/webhook';
import { registerMetaWebhook } from './routes/meta-webhook';
import { createDispatcher } from './dispatcher';

export function buildApp(pool: Pool): FastifyInstance {
  assertMetaEnv();

  const app = Fastify({ logger: true });

  // RAW body'ni saqlaydigan JSON parser — Meta signature tekshiruvi uchun SHART.
  app.addContentTypeParser(
    'application/json',
    { parseAs: 'buffer' },
    (req, body, done) => {
      (req as unknown as { rawBody?: Buffer }).rawBody = body as Buffer;
      try {
        const buf = body as Buffer;
        const json = buf.length ? JSON.parse(buf.toString('utf8')) : {};
        done(null, json);
      } catch (err) {
        done(err as Error, undefined);
      }
    },
  );

  const channels = new ChannelRepository(pool);
  const registry = new ConnectorRegistry();

  // Mavjud connector (per-channel URL pattern)
  registry.register('telegram', new TelegramConnector());

  // Meta connector — instagram va facebook UCHUN BITTA instansiya
  const meta = new MetaConnector(channels);
  registry.register('instagram', meta);
  registry.register('facebook', meta);

  const dispatch = createDispatcher(channels, (m) => app.log.info(m));

  // Route'lar
  registerChannelWebhook(app, registry, channels, dispatch);
  registerMetaWebhook(app, meta, dispatch);

  app.get('/health', async () => ({ ok: true, connectors: registry.types() }));

  return app;
}
