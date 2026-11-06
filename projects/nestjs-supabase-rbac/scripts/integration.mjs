// Own the complete disposable stack and always release it, including assertion failures.
import { spawn, spawnSync, execFileSync } from 'node:child_process';
import { mkdtempSync, writeFileSync, openSync, closeSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { setTimeout as pause } from 'node:timers/promises';
const dir = mkdtempSync(join(tmpdir(), 'clinic-rbac-'));
const cli = resolve('node_modules/.bin/supabase');
let edge;
let owned = false;
let failed = false;
let interrupted = false;
const children = new Set();
function stopGroup(child, signal = 'SIGTERM') {
  try { process.kill(-child.pid, signal); } catch (error) { if (error.code !== 'ESRCH') throw error; }
}
function ownedSpawn(command, args, options) {
  const child = spawn(command, args, { ...options, detached: true });
  children.add(child);
  child.once('exit', () => children.delete(child));
  return child;
}
const logPath = join(dir, 'stack.log');
const log = openSync(logPath, 'w');
const excluded = 'studio,realtime,storage-api,imgproxy,mailpit,logflare,vector,supavisor,postgres-meta';
async function run(command, args, options = {}) {
  if (interrupted) throw new Error('Interrupted');
  const child = ownedSpawn(command, args, { stdio: 'inherit', ...options });
  return await new Promise((res, rej) => { child.on('error', rej); child.on('exit', code => code === 0 ? res() : rej(new Error(`${command} exited ${code}`))); });
}
async function cleanup() {
  if (edge && edge.exitCode === null && edge.signalCode === null) {
    const stopped = new Promise(resolve => edge.once('exit', resolve));
    stopGroup(edge);
    await Promise.race([stopped, pause(5000)]);
    if (edge.exitCode === null && edge.signalCode === null) { stopGroup(edge, 'SIGKILL'); await stopped; }
  }
  if (owned) {
    const stop = spawnSync(cli, ['stop', '--no-backup'], { stdio: ['ignore', log, log], timeout: 60000 });
    const remaining = execFileSync('docker', ['ps', '-a', '--filter', 'label=com.supabase.cli.project=clinic-rbac', '--format', '{{.Names}}'], { encoding: 'utf8' }).trim();
    if (stop.status !== 0 || remaining) { failed = true; console.error('Cleanup needs attention:', remaining || 'Supabase stop failed'); }
    else console.log('Cleanup verified: no clinic-rbac containers remain.');
  }
  closeSync(log);
  rmSync(dir, { recursive: true, force: true });
}
for (const signal of ['SIGINT', 'SIGTERM']) process.once(signal, () => {
  interrupted = true;
  for (const child of children) stopGroup(child);
});
try {
  const existing = execFileSync('docker', ['ps', '-a', '--filter', 'label=com.supabase.cli.project=clinic-rbac', '--format', '{{.Names}}'], { encoding: 'utf8' }).trim();
  if (existing) throw new Error('Dedicated clinic-rbac stack already exists. Stop your demo explicitly before running this destructive local suite.');
  owned = true;
  console.log('Starting disposable local Supabase (Postgres, Auth, REST and edge runtime)...');
  await run(cli, ['start', '-x', excluded], { stdio: ['ignore', log, log] });
  const status = JSON.parse(execFileSync(cli, ['status', '-o', 'json'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }));
  const env = { ...process.env, SUPABASE_URL: status.API_URL, SUPABASE_ANON_KEY: status.ANON_KEY, SUPABASE_SERVICE_ROLE_KEY: status.SERVICE_ROLE_KEY,
    EDGE_TEST_URL: `${status.API_URL}/functions/v1/clinic-summary` };
  const gateway = execFileSync('docker', ['network', 'inspect', 'supabase_network_clinic-rbac', '--format', '{{(index .IPAM.Config 0).Gateway}}'], { encoding: 'utf8' }).trim();
  const apiHost = process.env.EDGE_API_HOST ?? (process.platform === 'darwin' ? 'host.docker.internal' : gateway);
  const edgeEnv = join(dir, 'edge.env');
  writeFileSync(edgeEnv, `API_BASE_URL=http://${apiHost}:3000\n`, { mode: 0o600 });
  edge = ownedSpawn(cli, ['functions', 'serve', '--env-file', edgeEnv], { stdio: ['ignore', log, log] });
  writeFileSync(join(dir, 'ownership.json'), JSON.stringify({ owner: 'clinic-rbac integration', pid: edge.pid, startedAt: new Date().toISOString(), ports: [3000, 54321, 54322], cleanup: `kill -TERM -- -${edge.pid}; npm run local:stop` }));
  let ready = false;
  for (let attempt = 0; attempt < 60; attempt++) {
    if (interrupted) throw new Error('Interrupted');
    try { const response = await fetch(`${env.EDGE_TEST_URL}?clinicId=10000000-0000-4000-8000-000000000001`, { signal: AbortSignal.timeout(2000) }); if (response.status === 401) { ready = true; break; } } catch {}
    if (edge.exitCode !== null || edge.signalCode !== null) throw new Error('Edge runtime exited before readiness');
    await pause(1000);
  }
  if (!ready) throw new Error('Edge runtime did not become ready');
  await run('npm', ['run', 'test:integration'], { env });
} catch (error) {
  failed = true;
  console.error(error.message);
  // Only error lines, with credentials redacted. Never dump status output or request content.
  const lines = readFileSync(logPath, 'utf8').split('\n').filter(line => /error|failed|exception/i.test(line)).slice(-10);
  for (const line of lines) console.error(line.replace(/eyJ[\w.-]+/g, '[redacted]').replace(/sb_(secret|publishable)_[\w-]+/g, '[redacted]'));
} finally { await cleanup(); }
process.exitCode = failed ? 1 : 0;
