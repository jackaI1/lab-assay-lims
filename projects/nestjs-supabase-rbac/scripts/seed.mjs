import { execFileSync, spawnSync } from 'node:child_process';
const status = JSON.parse(execFileSync('node_modules/.bin/supabase', ['status', '-o', 'json'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }));
const result = spawnSync(process.execPath, ['dist/test/seed.js'], { stdio: 'inherit', env: { ...process.env,
  SUPABASE_URL: status.API_URL, SUPABASE_ANON_KEY: status.ANON_KEY, SUPABASE_SERVICE_ROLE_KEY: status.SERVICE_ROLE_KEY } });
process.exitCode = result.status ?? 1;
