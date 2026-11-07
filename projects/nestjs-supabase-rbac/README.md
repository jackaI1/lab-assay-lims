# nestjs-supabase-rbac

I built a system that controls access to clinic records to learn how the underlying idea works. This is a learning project.

## Who can do what

| Default role | Patient details | Clinical notes | Appointments | Change access / read audit |
| --- | --- | --- | --- | --- |
| Admin | Clinic | None | Read and update clinic | Yes |
| Clinician | Assigned patients | Read, add and edit assigned | Read assigned | No |
| Receptionist | Clinic | None | Read and update clinic | No |
| Patient | Own record | Read own | Read own | No |

Nobody gets access to another clinic just by knowing its record IDs. Admins do not receive clinical note access by default. An admin can change individual permissions for a role within their clinic, or change an existing member's role. Each real change records the actor, target, time, and values before and after. The last admin cannot be removed, and the admin's recovery permissions stay enabled.

## Using the API

Every route except `GET /health` needs `Authorization: Bearer <Supabase access token>`. Supabase Auth handles sign-in and token verification. The demo script signs in the synthetic accounts for me.

| Route under `/clinics/:clinicId` | Purpose |
| --- | --- |
| `GET /patients`, `GET /patients/:id` | Visible patient details |
| `GET /notes`, `POST /notes`, `PATCH /notes/:id` | Read or write clinical notes |
| `GET /appointments`, `PATCH /appointments/:id` | Read appointments or change their status |
| `POST /permissions` | Enable or disable one permission for a role |
| `PATCH /members/:id` | Change an existing member's role |
| `GET /audit` | Read access changes |

For example, I can add a fictional note as the assigned clinician:

See [the walkthrough](docs/walkthrough.md) for permission changes, direct database requests, and the edge function. The API returns 401 for missing or invalid sign-in, 403 for missing permissions, and 404 when an individual record is outside the caller's visible set.

## How access stays consistent

NestJS organizes the API into controllers. My `@RequirePermission` decorator declares the action each route needs, and a global guard checks the signed-in user's current database permissions. A route without a permission declaration is denied unless I explicitly mark it public.

Supabase provides Postgres, sign-in, and a direct data API. Row-level security (RLS) means Postgres filters or rejects records for each signed-in user. The API passes the user's token to Supabase and uses the same permission table as those database policies. It never uses the elevated service-role key. Roles come from database memberships, not user-editable profile metadata, and I do not cache grants in tokens.

Clinical notes are in a separate table so appointment access cannot expose note text. Database column grants prevent callers from moving notes or appointments to another patient. Access changes happen through database functions that check the caller and write an audit entry in the same transaction. Ordinary users, including clinic admins, cannot directly edit the permission tables or rewrite the audit history.

The serverless `clinic-summary` edge function runs on Supabase's edge runtime and calls this API with the caller's token. It returns the appointments that caller can see. Its API address comes from configuration, and it needs no elevated database key. [Design notes](docs/design.md) explain the boundaries and limitations.

## Tests and limits

There are 4 test source files in this copy. That source count does not establish an execution result. This is a source snapshot, and running it on a new machine may need environment-specific setup.



Retained project workflows: `nestjs-supabase-rbac-ci.yml`. Their commands use this folder and their triggers use its paths.
