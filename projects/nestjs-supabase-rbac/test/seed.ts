import { writeFileSync } from 'node:fs';
import { clinicA, fixture } from './fixtures';
fixture().then(({ accounts }) => {
  const values = { SUPABASE_URL: process.env.SUPABASE_URL!, SUPABASE_ANON_KEY: process.env.SUPABASE_ANON_KEY!, CLINIC_ID: clinicA,
    DEMO_TOKEN: accounts.clinician.token, PATIENT_TOKEN: accounts.patient.token, ADMIN_TOKEN: accounts.admin.token };
  writeFileSync('.env.demo', Object.entries(values).map(([key, value]) => `export ${key}='${value}'`).join('\n') + '\n', { mode: 0o600 });
  console.log('Created two fictional clinics and seven synthetic accounts. Local demo tokens are in ignored .env.demo; do not commit or share it.');
}).catch(() => { console.error('Fixture setup failed. Start the dedicated local stack first.'); process.exitCode = 1; });
