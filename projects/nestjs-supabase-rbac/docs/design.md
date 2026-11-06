# Access model and limits

I put the source of access decisions in Postgres: `memberships` assigns one role per user per clinic, and `role_permissions` holds that clinic's grants. Seven permissions cover patient reads, note reads/writes, appointment reads/writes, role management, and audit reads. The API asks `has_permission` on each request. Policies ask the same function and apply the patient's ownership or clinician assignment as a second condition.

```text
Supabase Auth token -> optional edge function -> Nest global guard -> controller
                                                 |                   |
                                                 +-> permission RPC  +-> user's Supabase client
                                                                          |
                                                               Postgres grants + RLS
```

`private.member_role` and `private.can_reach_patient` avoid recursive policies. These small security-definer helpers use a fixed empty search path and fully qualified object names. They return only the caller's role or an access boolean. Management functions check `roles.manage`, serialize changes, and append audit entries transactionally. Function execution privileges are explicitly removed from anonymous callers. No API route accepts a caller-supplied author or clinic field in the body.

The two management functions are the only authenticated write path to memberships and permissions. Ordinary clinic admins cannot alter audit entries. A database operator or a stolen service-role key can still bypass these controls. This is an application audit trail, not an external tamper-proof ledger.

The role and row scopes are distinct. Granting `notes.read` to reception intentionally exposes clinic notes, since reception has clinic-wide row scope. Granting `appointments.write` to a clinician still only permits assigned records. Permissions do not grant membership in another clinic. A changed membership or permission is read from the database on the next request, including requests using an already-issued token.

Patients can read all notes on their own record in this fictional workflow. Real clinics may need separate release/review rules before sharing notes. Admins can grant themselves clinical permissions, and these changes are audited. This is an explicit access-management trust boundary.

Records and assignments are bootstrapped by a trusted operator. There are no patient-registration, prescription, billing or scheduling-conflict features. Lists are small and not paginated; production would need pagination, rate limits, retention rules, operational monitoring, consent/release rules and a privacy/security review. Nothing here establishes compliance for handling medical data.

## Local resource ownership

`scripts/integration.mjs` refuses to take over an existing `clinic-rbac` stack. It starts its own Supabase containers, records the edge process PID/start time and ports in a temporary ownership file, stops the process and containers in `finally`, and checks Docker metadata afterward. The API test listener on port 3000 is closed by the test runner's teardown. Local Supabase uses 54321 for HTTP and 54322 for Postgres; the remaining ports are in `supabase/config.toml`. CI has an additional always-run stop step for cancellation.
