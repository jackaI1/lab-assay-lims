import { after, before, test } from 'node:test';
import assert from 'node:assert/strict';
import request from 'supertest';
import type { INestApplication } from '@nestjs/common';
import { createApp } from '../src/app';
import { Account, appointmentA, appointmentB, clinicA, clinicB, defaults, fixture, noteA, noteB, ok, patientA, patientB } from './fixtures';
let app: INestApplication;
let data: Awaited<ReturnType<typeof fixture>>;
const path = (suffix: string, cid = clinicA) => `/clinics/${cid}/${suffix}`;
const api = (name: Account, method: 'get' | 'post' | 'patch', suffix: string, cid = clinicA) =>
  request(app.getHttpServer())[method](path(suffix, cid)).set('Authorization', `Bearer ${data.accounts[name].token}`);
before(async () => {
  data = await fixture();
  app = await createApp();
  await app.listen(3000, '0.0.0.0');
});
after(async () => { if (app) await app.close(); });

const matrix: { role: Account; patients: string[]; notes: number; appointments: number }[] = [
  { role: 'admin', patients: [patientA, patientB], notes: -1, appointments: 2 },
  { role: 'clinician', patients: [patientA], notes: 1, appointments: 1 },
  { role: 'receptionist', patients: [patientA, patientB], notes: -1, appointments: 2 },
  { role: 'patient', patients: [patientA], notes: 1, appointments: 1 },
];
for (const row of matrix) {
  test(`${row.role}: API returns only permitted patients, notes and appointments`, async () => {
    const patients = await api(row.role, 'get', 'patients').expect(200);
    assert.deepEqual(patients.body.map((p: { id: string }) => p.id).sort(), row.patients);
    const notes = await api(row.role, 'get', 'notes').expect(row.notes < 0 ? 403 : 200);
    if (row.notes >= 0) assert.equal(notes.body.length, row.notes);
    const appointments = await api(row.role, 'get', 'appointments').expect(200);
    assert.equal(appointments.body.length, row.appointments);
  });
  test(`${row.role}: direct Supabase reads preserve the same row boundaries`, async () => {
    const db = data.accounts[row.role].db;
    assert.deepEqual(ok(await db.from('patients').select('id')).map(p => p.id).sort(), row.patients);
    assert.equal(ok(await db.from('notes').select('id')).length, Math.max(row.notes, 0));
    assert.equal(ok(await db.from('appointments').select('id')).length, row.appointments);
    assert.equal(ok(await db.from('permission_audit').select('*')).length, 0);
  });
  test(`${row.role}: another clinic is denied by both API and RLS`, async () => {
    await api(row.role, 'get', 'patients', clinicB).expect(403);
    for (const table of ['patients', 'notes', 'appointments', 'permission_audit']) {
      assert.deepEqual(ok(await data.accounts[row.role].db.from(table).select('*').eq('clinic_id', clinicB)), []);
    }
  });
  test(`${row.role}: permission RPC agrees with its default grants`, async () => {
    const db = data.accounts[row.role].db;
    const all = ['patients.read', 'notes.read', 'notes.write', 'appointments.read', 'appointments.write', 'roles.manage', 'audit.read'];
    for (const wanted of all) assert.equal(ok(await db.rpc('has_permission', { cid: clinicA, wanted })), (defaults[row.role as keyof typeof defaults] as readonly string[]).includes(wanted));
  });
}
test('invalid, missing and tampered identity is rejected', async () => {
  await request(app.getHttpServer()).get(path('patients')).expect(401);
  await request(app.getHttpServer()).get(path('patients')).set('Authorization', 'Bearer forged').expect(401);
  const token = data.accounts.patient.token;
  const [header, payload, signature] = token.split('.');
  const claims = JSON.parse(Buffer.from(payload, 'base64url').toString());
  claims.sub = data.accounts.admin.id;
  const forged = [header, Buffer.from(JSON.stringify(claims)).toString('base64url'), signature].join('.');
  await request(app.getHttpServer()).get(path('audit')).set('Authorization', `Bearer ${forged}`).expect(401);
});
test('user-editable metadata cannot grant administrator rights', async () => {
  ok(await data.accounts.patient.db.auth.updateUser({ data: { role: 'admin', permissions: ['roles.manage'] } }));
  await api('patient', 'get', 'audit').expect(403);
  const result = await data.accounts.patient.db.rpc('set_role_permission', { cid: clinicA, target_role: 'patient', wanted: 'roles.manage', enabled: true });
  assert.equal(result.error?.code, '42501');
});
test('unassigned records return 404 without revealing whether the ID exists', async () => {
  await api('clinician', 'get', `patients/${patientB}`).expect(404);
  await api('patient', 'get', `patients/${patientB}`).expect(404);
  await api('otherClinician', 'get', `patients/${patientA}`).expect(404);
  await api('outsider', 'get', 'patients').expect(403);
});
for (const name of ['admin', 'receptionist', 'patient'] as const) {
  test(`${name}: cannot add clinical notes`, async () => {
    await api(name, 'post', 'notes').send({ patient_id: patientA, body: 'Forbidden' }).expect(403);
    const result = await data.accounts[name].db.from('notes').insert({ clinic_id: clinicA, patient_id: patientA, body: 'Forbidden' });
    assert.equal(result.error?.code, '42501');
  });
}
test('clinician writes and edits assigned notes, but cannot reach unassigned records', async () => {
  const created = await api('clinician', 'post', 'notes').send({ patient_id: patientA, body: 'Synthetic follow-up.' }).expect(201);
  assert.equal(created.body.author_id, data.accounts.clinician.id);
  await api('clinician', 'patch', `notes/${created.body.id}`).send({ body: 'Synthetic revision.' }).expect(200);
  await api('clinician', 'patch', `notes/${noteB}`).send({ body: 'Forbidden' }).expect(404);
  await api('clinician', 'post', 'notes').send({ patient_id: patientB, body: 'Forbidden' }).expect(403);
  const direct = await data.accounts.clinician.db.from('notes').update({ body: 'Forbidden' }).eq('id', noteB).select();
  assert.deepEqual(ok(direct), []);
  const spoof = await data.accounts.clinician.db.from('notes').insert({ clinic_id: clinicA, patient_id: patientA, body: 'Spoof', author_id: data.accounts.admin.id });
  assert.equal(spoof.error?.code, '42501');
  const cross = await data.accounts.clinician.db.from('notes').insert({ clinic_id: clinicA, patient_id: '20000000-0000-4000-8000-000000000003', body: 'Cross clinic' });
  assert.equal(cross.error?.code, '42501');
});
for (const role of ['admin', 'receptionist', 'clinician', 'patient'] as const) {
  test(`${role}: appointment writes follow the permission matrix`, async () => {
    const allowed = role === 'admin' || role === 'receptionist';
    await api(role, 'patch', `appointments/${appointmentA}`).send({ status: 'arrived' }).expect(allowed ? 200 : 403);
    const direct = ok(await data.accounts[role].db.from('appointments').update({ status: 'scheduled' }).eq('id', appointmentB).select());
    assert.equal(direct.length, allowed ? 1 : 0);
  });
}
test('DTOs reject field smuggling, malformed IDs and invalid states', async () => {
  await api('clinician', 'post', 'notes').send({ patient_id: patientA, body: 'Test', author_id: data.accounts.admin.id }).expect(400);
  await api('clinician', 'post', 'notes').send({ patient_id: patientA, body: '' }).expect(400);
  await api('clinician', 'post', 'notes').send({ patient_id: patientA, body: 'x'.repeat(4001) }).expect(400);
  await api('receptionist', 'patch', `appointments/${appointmentA}`).send({ status: 'unknown' }).expect(400);
  await api('receptionist', 'patch', `appointments/${appointmentA}`).send({ status: 'arrived', clinic_id: clinicB }).expect(400);
  await api('patient', 'get', 'patients/not-a-uuid').expect(400);
});
test('RLS blocks moving records, raw permission changes and audit tampering', async () => {
  for (const role of ['admin', 'clinician', 'receptionist', 'patient'] as const) {
    const db = data.accounts[role].db;
    assert.equal((await db.from('memberships').update({ role: 'admin' }).eq('user_id', data.accounts.patient.id)).error?.code, '42501');
    assert.equal((await db.from('role_permissions').insert({ clinic_id: clinicA, role: 'patient', permission: 'roles.manage' })).error?.code, '42501');
    assert.equal((await db.from('notes').update({ patient_id: patientB }).eq('id', noteA)).error?.code, '42501');
    assert.equal((await db.from('appointments').update({ clinic_id: clinicB }).eq('id', appointmentA)).error?.code, '42501');
    assert.equal((await db.from('permission_audit').insert({ clinic_id: clinicA, actor_id: data.accounts.admin.id, action: 'fake', target: 'fake' })).error?.code, '42501');
    assert.equal((await db.from('permission_audit').delete().eq('clinic_id', clinicA)).error?.code, '42501');
  }
});
test('revoking a fine-grained permission takes effect immediately and is audited once', async () => {
  const payload = { role: 'clinician', permission: 'notes.write', enabled: false };
  await api('admin', 'post', 'permissions').send(payload).expect(204);
  try {
    await api('clinician', 'post', 'notes').send({ patient_id: patientA, body: 'Revoked' }).expect(403);
    assert.equal((await data.accounts.clinician.db.from('notes').insert({ clinic_id: clinicA, patient_id: patientA, body: 'Revoked' })).error?.code, '42501');
    await api('clinician', 'get', 'notes').expect(200);
    await api('admin', 'post', 'permissions').send(payload).expect(204);
    const audit = await api('admin', 'get', 'audit').expect(200);
    assert.equal(audit.body.length, 1);
    assert.equal(audit.body[0].actor_id, data.accounts.admin.id);
    assert.equal(audit.body[0].target, 'clinician:notes.write');
    assert.equal(audit.body[0].before_value, true);
    assert.equal(audit.body[0].after_value, false);
    await api('clinician', 'get', 'audit').expect(403);
    await api('outsider', 'post', 'permissions').send(payload).expect(403);
  } finally { await api('admin', 'post', 'permissions').send({ ...payload, enabled: true }).expect(204); }
});
test('only administrators can change membership and changes are audited', async () => {
  await api('patient', 'patch', `members/${data.accounts.patient.id}`).send({ role: 'admin' }).expect(403);
  await api('admin', 'patch', `members/${data.accounts.admin.id}`).send({ role: 'patient' }).expect(400);
  await api('admin', 'post', 'permissions').send({ role: 'admin', permission: 'roles.manage', enabled: false }).expect(400);
  await api('admin', 'patch', `members/${data.accounts.receptionist.id}`).send({ role: 'patient' }).expect(204);
  try {
    await api('receptionist', 'patch', `appointments/${appointmentA}`).send({ status: 'arrived' }).expect(403);
    const audit = await api('admin', 'get', 'audit').expect(200);
    assert.ok(audit.body.some((e: { action: string; before_value: string; after_value: string }) => e.action === 'member_role' && e.before_value === 'receptionist' && e.after_value === 'patient'));
  } finally { await api('admin', 'patch', `members/${data.accounts.receptionist.id}`).send({ role: 'receptionist' }).expect(204); }
});
test('anonymous database clients cannot read records or execute management RPCs', async () => {
  const { createClient } = await import('@supabase/supabase-js');
  const anon = createClient(process.env.SUPABASE_URL!, process.env.SUPABASE_ANON_KEY!);
  assert.equal((await anon.from('patients').select('*')).error?.code, '42501');
  assert.ok((await anon.rpc('set_member_role', { cid: clinicA, member_id: data.accounts.patient.id, new_role: 'admin' })).error);
});
for (const role of ['admin', 'clinician', 'receptionist', 'patient'] as const) {
  test(`${role}: deployed local edge function forwards identity and returns only allowed appointments`, async () => {
    assert.ok(process.env.EDGE_TEST_URL, 'Run scripts/integration.sh to start the real edge runtime');
    const response = await fetch(`${process.env.EDGE_TEST_URL}?clinicId=${clinicA}`, { headers: { Authorization: `Bearer ${data.accounts[role].token}` } });
    assert.equal(response.status, 200, await response.clone().text());
    const body = await response.json() as { appointments: { patient_id: string }[] };
    assert.equal(body.appointments.length, role === 'admin' || role === 'receptionist' ? 2 : 1);
    const foreign = await fetch(`${process.env.EDGE_TEST_URL}?clinicId=${clinicB}`, { headers: { Authorization: `Bearer ${data.accounts[role].token}` } });
    assert.equal(foreign.status, 403);
  });
}
test('real edge function rejects missing and forged tokens', async () => {
  assert.equal((await fetch(`${process.env.EDGE_TEST_URL}?clinicId=${clinicA}`)).status, 401);
  assert.equal((await fetch(`${process.env.EDGE_TEST_URL}?clinicId=${clinicA}`, { headers: { Authorization: 'Bearer forged' } })).status, 401);
});
test('granting a clinician appointment writes keeps the assigned-patient boundary', async () => {
  const payload = { role: 'clinician', permission: 'appointments.write', enabled: true };
  await api('admin', 'post', 'permissions').send(payload).expect(204);
  try {
    await api('clinician', 'patch', `appointments/${appointmentA}`).send({ status: 'arrived' }).expect(200);
    await api('clinician', 'patch', `appointments/${appointmentB}`).send({ status: 'arrived' }).expect(404);
    assert.deepEqual(ok(await data.accounts.clinician.db.from('appointments').update({ status: 'arrived' }).eq('id', appointmentB).select()), []);
  } finally { await api('admin', 'post', 'permissions').send({ ...payload, enabled: false }).expect(204); }
});
test('patients cannot edit their own notes, even through the direct data API', async () => {
  await api('patient', 'patch', `notes/${noteA}`).send({ body: 'Forbidden edit' }).expect(403);
  assert.deepEqual(ok(await data.accounts.patient.db.from('notes').update({ body: 'Forbidden edit' }).eq('id', noteA).select()), []);
  const notes = ok(await data.accounts.patient.db.from('notes').select('body').eq('id', noteA));
  assert.equal(notes[0].body, 'Synthetic follow-up note A.');
});
