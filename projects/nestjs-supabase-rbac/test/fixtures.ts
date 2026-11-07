import { createClient, SupabaseClient } from '@supabase/supabase-js';
import assert from 'node:assert/strict';
import { randomBytes, randomUUID } from 'node:crypto';
export const clinicA = '10000000-0000-4000-8000-000000000001';
export const clinicB = '10000000-0000-4000-8000-000000000002';
export const patientA = '20000000-0000-4000-8000-000000000001';
export const patientB = '20000000-0000-4000-8000-000000000002';
export const patientC = '20000000-0000-4000-8000-000000000003';
export const appointmentA = '30000000-0000-4000-8000-000000000001';
export const appointmentB = '30000000-0000-4000-8000-000000000002';
export const noteA = '40000000-0000-4000-8000-000000000001';
export const noteB = '40000000-0000-4000-8000-000000000002';
export const accountNames = ['admin', 'clinician', 'otherClinician', 'receptionist', 'patient', 'otherPatient', 'outsider'] as const;
export type Account = typeof accountNames[number];
export const defaults = {
  admin: ['patients.read', 'appointments.read', 'appointments.write', 'roles.manage', 'audit.read'],
  clinician: ['patients.read', 'notes.read', 'notes.write', 'appointments.read'],
  receptionist: ['patients.read', 'appointments.read', 'appointments.write'],
  patient: ['patients.read', 'notes.read', 'appointments.read'],
} as const;
export function localAdmin() {
  const url = process.env.SUPABASE_URL ?? '';
  if (!['127.0.0.1', 'localhost'].includes(new URL(url).hostname)) throw new Error('Fixtures only run against local Supabase');
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!key) throw new Error('Local SUPABASE_SERVICE_ROLE_KEY required for fixtures');
  return createClient(url, key, { auth: { persistSession: false, autoRefreshToken: false } });
}
export function ok<T extends { data: unknown; error: unknown }>(result: T): NonNullable<T['data']> { assert.equal(result.error, null, JSON.stringify(result.error)); return result.data as NonNullable<T['data']>; }
export async function fixture() {
  const admin = localAdmin();
  const accounts = {} as Record<Account, { id: string; token: string; db: SupabaseClient; email: string; password: string }>;
  // Repeatable only on this dedicated synthetic project. No personal identities are used.
  for (const table of ['permission_audit', 'notes', 'appointments', 'patients', 'role_permissions', 'memberships', 'clinics']) ok(await admin.from(table).delete().not(['memberships', 'role_permissions'].includes(table) ? 'clinic_id' : 'id', 'is', null));
  const existing = ok(await admin.auth.admin.listUsers()).users;
  for (const user of existing.filter(u => u.email?.endsWith('@clinic.example.test'))) ok(await admin.auth.admin.deleteUser(user.id));
  try {
    for (const name of accountNames) {
      const email = `${name.toLowerCase()}@clinic.example.test`;
      const password = randomBytes(24).toString('base64url');
      const user = ok(await admin.auth.admin.createUser({ email, password, email_confirm: true })).user!;
      const db = createClient(process.env.SUPABASE_URL!, process.env.SUPABASE_ANON_KEY!, { auth: { persistSession: false, autoRefreshToken: false } });
      const session = ok(await db.auth.signInWithPassword({ email, password })).session!;
      accounts[name] = { id: user.id, token: session.access_token, db, email, password };
    }
    ok(await admin.from('clinics').insert([{ id: clinicA, name: 'Maple Demo Clinic' }, { id: clinicB, name: 'Cedar Demo Clinic' }]));
    ok(await admin.from('memberships').insert([
      ...accountNames.filter(n => n !== 'outsider').map(name => ({ clinic_id: clinicA, user_id: accounts[name].id, role: name === 'otherClinician' ? 'clinician' : name === 'otherPatient' ? 'patient' : name })),
      { clinic_id: clinicB, user_id: accounts.outsider.id, role: 'admin' },
    ]));
    ok(await admin.from('role_permissions').insert([clinicA, clinicB].flatMap(cid => Object.entries(defaults).flatMap(([role, perms]) => perms.map(permission => ({ clinic_id: cid, role, permission }))))));
    ok(await admin.from('patients').insert([
      { id: patientA, clinic_id: clinicA, user_id: accounts.patient.id, clinician_id: accounts.clinician.id, display_name: 'Demo Patient A' },
      { id: patientB, clinic_id: clinicA, user_id: accounts.otherPatient.id, clinician_id: accounts.otherClinician.id, display_name: 'Demo Patient B' },
      { id: patientC, clinic_id: clinicB, user_id: accounts.outsider.id, clinician_id: accounts.outsider.id, display_name: 'Demo Patient C' },
    ]));
    ok(await admin.from('notes').insert([
      { id: noteA, clinic_id: clinicA, patient_id: patientA, body: 'Synthetic follow-up note A.', author_id: accounts.clinician.id },
      { id: noteB, clinic_id: clinicA, patient_id: patientB, body: 'Synthetic follow-up note B.', author_id: accounts.otherClinician.id },
      { id: randomUUID(), clinic_id: clinicB, patient_id: patientC, body: 'Synthetic other clinic note.', author_id: accounts.outsider.id },
    ]));
    ok(await admin.from('appointments').insert([
      { id: appointmentA, clinic_id: clinicA, patient_id: patientA, starts_at: '2030-01-02T10:00:00Z' },
      { id: appointmentB, clinic_id: clinicA, patient_id: patientB, starts_at: '2030-01-02T11:00:00Z' },
      { id: randomUUID(), clinic_id: clinicB, patient_id: patientC, starts_at: '2030-01-02T12:00:00Z' },
    ]));
    return { admin, accounts };
  } catch (error) {
    for (const account of Object.values(accounts)) await admin.auth.admin.deleteUser(account.id);
    throw error;
  }
}
