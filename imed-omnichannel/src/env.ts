import 'dotenv/config';

/**
 * Muhit o'zgaruvchilari. Import paytida XATO tashlamaymiz — shunda migratsiya
 * (faqat DATABASE_URL kerak) va typecheck Meta kalitlarisiz ham ishlaydi.
 * Meta kalitlari faqat serverni ko'targanda (buildApp) tekshiriladi.
 */
export const env = {
  PORT: Number(process.env.PORT ?? 3000),
  DATABASE_URL: process.env.DATABASE_URL ?? '',
  META_APP_SECRET: process.env.META_APP_SECRET ?? '',
  META_VERIFY_TOKEN: process.env.META_VERIFY_TOKEN ?? '',
  META_GRAPH_VERSION: process.env.META_GRAPH_VERSION ?? 'v21.0',
  TELEGRAM_BOT_TOKEN: process.env.TELEGRAM_BOT_TOKEN ?? '',
};

export function assertDatabaseEnv(): void {
  if (!env.DATABASE_URL) {
    throw new Error('DATABASE_URL env berilmagan');
  }
}

export function assertMetaEnv(): void {
  const missing: string[] = [];
  if (!env.META_APP_SECRET) missing.push('META_APP_SECRET');
  if (!env.META_VERIFY_TOKEN) missing.push('META_VERIFY_TOKEN');
  if (missing.length) {
    throw new Error(`Meta connector uchun env yetishmaydi: ${missing.join(', ')}`);
  }
}
