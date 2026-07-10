import crypto from 'node:crypto';

/**
 * X-Hub-Signature-256 tekshiruvi.
 * Meta body'ni app_secret bilan HMAC-SHA256 qiladi va 'sha256=<hex>' yuboradi.
 * MUHIM: hisob-kitob O'ZGARTIRILMAGAN raw body ustidan bo'lishi shart.
 */
export function verifySignature(
  appSecret: string,
  rawBody: Buffer,
  header: string | undefined,
): boolean {
  if (!header) return false;
  const expected =
    'sha256=' + crypto.createHmac('sha256', appSecret).update(rawBody).digest('hex');
  const a = Buffer.from(expected, 'utf8');
  const b = Buffer.from(header, 'utf8');
  if (a.length !== b.length) return false;
  return crypto.timingSafeEqual(a, b);
}
