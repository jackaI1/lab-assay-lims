import { test } from 'node:test';
import assert from 'node:assert/strict';
import request from 'supertest';
import { createApp } from '../src/app';
import { summaryHandler } from '../supabase/functions/_shared/summary.js';

test('health is public and protected routes reject missing credentials', async () => {
  const app = await createApp();
  try {
    await request(app.getHttpServer()).get('/health').expect(200, { status: 'ok' });
    await request(app.getHttpServer()).get('/clinics/10000000-0000-4000-8000-000000000001/patients').expect(401);
  } finally { await app.close(); }
});
test('edge rejects missing identity before attempting the API', async () => {
  const handle = summaryHandler('http://unused', async () => { throw Error('Must not call upstream'); });
  assert.equal((await handle(new Request('http://edge/?clinicId=x'))).status, 401);
});
test('edge rejects unsupported methods and malformed clinic IDs', async () => {
  const handle = summaryHandler('http://unused');
  assert.equal((await handle(new Request('http://edge', { method: 'POST' }))).status, 405);
  assert.equal((await handle(new Request('http://edge/?clinicId=../x', { headers: { Authorization: 'Bearer test' } }))).status, 400);
});
test('edge bounds upstream failures and does not expose upstream error bodies', async () => {
  const handle = summaryHandler('http://unused', async () => new Response('private backend details', { status: 500 }));
  const response = await handle(new Request('http://edge/?clinicId=10000000-0000-4000-8000-000000000001', { headers: { Authorization: 'Bearer test' } }));
  assert.equal(response.status, 502);
  assert.ok(!(await response.text()).includes('private backend details'));
});
