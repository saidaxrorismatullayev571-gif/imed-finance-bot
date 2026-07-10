import type { FastifyRequest } from 'fastify';
import type { WebhookContext } from '../connectors/connector';

/** Fastify so'rovidan connectorlar uchun WebhookContext yasaydi. */
export function buildContext(
  req: FastifyRequest,
  method: 'GET' | 'POST',
): WebhookContext {
  const headers: Record<string, string | undefined> = {};
  for (const [k, v] of Object.entries(req.headers)) {
    headers[k] = Array.isArray(v) ? v[0] : v;
  }

  const query: Record<string, string | undefined> = {};
  const q = (req.query ?? {}) as Record<string, unknown>;
  for (const [k, v] of Object.entries(q)) {
    query[k] = v == null ? undefined : String(v);
  }

  // rawBody content-type parser tomonidan biriktiriladi (imzo tekshiruvi uchun).
  const attached = (req as unknown as { rawBody?: Buffer }).rawBody;
  const rawBody =
    attached instanceof Buffer
      ? attached
      : Buffer.from(
          typeof req.body === 'string' ? req.body : JSON.stringify(req.body ?? {}),
          'utf8',
        );

  return { method, headers, query, rawBody, body: req.body };
}
