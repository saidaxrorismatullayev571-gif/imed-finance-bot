import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { Pool } from 'pg';
import { env, assertDatabaseEnv } from '../env';

/** Oddiy, tartibli migratsiya ijrochisi (_migrations jadvaliga tayanadi). */
async function main(): Promise<void> {
  assertDatabaseEnv();
  const pool = new Pool({ connectionString: env.DATABASE_URL });

  await pool.query(
    `CREATE TABLE IF NOT EXISTS _migrations (
       name text PRIMARY KEY,
       applied_at timestamptz NOT NULL DEFAULT now()
     )`,
  );

  const dir = join(__dirname, 'migrations');
  const files = readdirSync(dir)
    .filter((f) => f.endsWith('.sql'))
    .sort();

  for (const file of files) {
    const done = await pool.query('SELECT 1 FROM _migrations WHERE name = $1', [file]);
    if (done.rowCount) {
      console.log(`o'tkazib yuborildi: ${file}`);
      continue;
    }
    const sql = readFileSync(join(dir, file), 'utf8');
    console.log(`qo'llanmoqda: ${file}`);
    await pool.query('BEGIN');
    try {
      await pool.query(sql);
      await pool.query('INSERT INTO _migrations(name) VALUES ($1)', [file]);
      await pool.query('COMMIT');
    } catch (err) {
      await pool.query('ROLLBACK');
      throw err;
    }
  }

  await pool.end();
  console.log('migratsiyalar tayyor ✅');
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
