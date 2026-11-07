# Trying access changes

I use the local demo from the README first. These commands assume `.env.demo` has been sourced and the API is running. Everything is synthetic. Re-seeding clears this dedicated project's records.

## Revoke one action

I can remove note-writing access from clinicians while keeping their read access:

```sh
curl -i -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"role":"clinician","permission":"notes.write","enabled":false}' \
  "http://localhost:3000/clinics/$CLINIC_ID/permissions"
```

A 204 means the change succeeded. Repeating the note POST in the README now returns 403 with the same clinician token. Reading notes still works. To restore writing, repeat the request with `"enabled":true`.

```sh
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  "http://localhost:3000/clinics/$CLINIC_ID/audit"
```

Each change appears with its actor and before/after values. Repeating a change that is already in effect does not add another entry.

## Try the database boundary directly

This request skips NestJS and still returns only the assigned patient's details:

```sh
curl -H "apikey: $SUPABASE_ANON_KEY" \
  -H "Authorization: Bearer $DEMO_TOKEN" \
  "$SUPABASE_URL/rest/v1/patients?select=*"
```

Use `$PATIENT_TOKEN` to see only that patient's own record. RLS also protects writes and rejects cross-clinic records. The elevated service-role key is only used by the local fixture setup. It deliberately bypasses RLS and must never be put in a client or the API environment.

## Serve the edge function

Keep the API running on port 3000. The API must be reachable from the edge container. On Docker Desktop or Colima on macOS, create a local ignored environment file:

```sh
printf 'API_BASE_URL=http://host.docker.internal:3000\n' > .env.edge
npx supabase functions serve --env-file .env.edge
```

On a Linux Docker engine, use the gateway from `docker network inspect supabase_network_clinic-rbac --format '{{(index .IPAM.Config 0).Gateway}}'` in place of `host.docker.internal`.

In another terminal:

```sh
source .env.demo
curl -H "Authorization: Bearer $PATIENT_TOKEN" \
  "$SUPABASE_URL/functions/v1/clinic-summary?clinicId=$CLINIC_ID"
```

The function forwards the patient's token to NestJS and returns their appointments. It rejects missing tokens and lets the API validate signed tokens. `verify_jwt=false` in the function configuration avoids a second gateway JWT implementation; it does not make API data public. Stop the function with Ctrl+C, stop the API with Ctrl+C, then run `npm run local:stop`.

## Environment and deployment

For a hosted sandbox, apply `supabase/migrations/202611060001_clinic.sql`, configure the API with `SUPABASE_URL`, `SUPABASE_ANON_KEY` and optionally `PORT`, and use normal Supabase Auth sign-in. An operator must bootstrap real clinic memberships and role grants through a trusted database connection. The local seeder refuses remote URLs and is not a production onboarding tool.

Set `API_BASE_URL` as a Supabase function secret pointing at the deployed HTTPS API, then deploy `clinic-summary`. The shared handler is inside `supabase/functions/_shared`, so it is packaged with the function. Keep the public anonymous/publishable key separate from the private service-role key. Never deploy the demo tokens or use real patient information here.
