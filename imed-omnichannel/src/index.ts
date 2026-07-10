import { Pool } from 'pg';
import { env, assertDatabaseEnv } from './env';
import { buildApp } from './app';

async function main(): Promise<void> {
  assertDatabaseEnv();
  const pool = new Pool({ connectionString: env.DATABASE_URL });
  const app = buildApp(pool);
  await app.listen({ port: env.PORT, host: '0.0.0.0' });
  app.log.info(`imed-omnichannel ishga tushdi: port ${env.PORT}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
