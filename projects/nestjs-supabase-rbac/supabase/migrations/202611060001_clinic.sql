-- All identities and clinic memberships live in Postgres, never user-editable JWT metadata.
create type public.clinic_role as enum ('admin', 'clinician', 'receptionist', 'patient');
create type public.clinic_permission as enum (
  'patients.read', 'notes.read', 'notes.write', 'appointments.read',
  'appointments.write', 'roles.manage', 'audit.read'
);
create table public.clinics (id uuid primary key default gen_random_uuid(), name text not null);
create table public.memberships (
  clinic_id uuid references public.clinics on delete cascade,
  user_id uuid references auth.users on delete cascade,
  role public.clinic_role not null,
  primary key (clinic_id, user_id)
);
create table public.role_permissions (
  clinic_id uuid references public.clinics on delete cascade,
  role public.clinic_role not null,
  permission public.clinic_permission not null,
  primary key (clinic_id, role, permission)
);
create table public.patients (
  id uuid primary key default gen_random_uuid(),
  clinic_id uuid not null references public.clinics,
  user_id uuid not null references auth.users,
  clinician_id uuid not null references auth.users,
  display_name text not null,
  unique (clinic_id, id), unique(clinic_id, user_id),
  foreign key (clinic_id, user_id) references public.memberships(clinic_id, user_id),
  foreign key (clinic_id, clinician_id) references public.memberships(clinic_id, user_id)
);
create table public.notes (
  id uuid primary key default gen_random_uuid(),
  clinic_id uuid not null,
  patient_id uuid not null,
  body text not null check (length(body) between 1 and 4000),
  author_id uuid not null default auth.uid() references auth.users,
  created_at timestamptz not null default now(),
  foreign key (clinic_id, patient_id) references public.patients(clinic_id, id)
);
create table public.appointments (
  id uuid primary key default gen_random_uuid(),
  clinic_id uuid not null,
  patient_id uuid not null,
  starts_at timestamptz not null,
  status text not null default 'scheduled' check(status in ('scheduled', 'arrived', 'cancelled')),
  foreign key (clinic_id, patient_id) references public.patients(clinic_id, id)
);
create table public.permission_audit (
  id bigint generated always as identity primary key,
  clinic_id uuid not null references public.clinics,
  actor_id uuid not null references auth.users,
  target text not null,
  action text not null,
  before_value jsonb,
  after_value jsonb,
  created_at timestamptz not null default now()
);
create schema private;
revoke all on schema private from public;
grant usage on schema private to authenticated;
create function private.member_role(cid uuid) returns public.clinic_role
language sql stable security definer set search_path = '' as $$
  select role from public.memberships where clinic_id = cid and user_id = auth.uid();
$$;
create function public.has_permission(cid uuid, wanted public.clinic_permission) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists(select 1 from public.memberships m join public.role_permissions p
    on p.clinic_id=m.clinic_id and p.role=m.role
    where m.clinic_id=cid and m.user_id=auth.uid() and p.permission=wanted);
$$;
create function private.can_reach_patient(cid uuid, pid uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists(select 1 from public.patients p where p.clinic_id=cid and p.id=pid and (
    private.member_role(cid) in ('admin', 'receptionist') or
    (private.member_role(cid)='clinician' and p.clinician_id=auth.uid()) or
    (private.member_role(cid)='patient' and p.user_id=auth.uid())
  ));
$$;
-- Management is transactional: changing access and recording who did it succeed together.
create function public.set_role_permission(cid uuid, target_role public.clinic_role,
  wanted public.clinic_permission, enabled boolean) returns void
language plpgsql security definer set search_path = '' as $$
declare was_enabled boolean;
begin
  if not public.has_permission(cid, 'roles.manage') then
    raise exception 'Permission denied' using errcode='42501';
  end if;
  if target_role='admin' and wanted in ('roles.manage','audit.read') then
    raise exception 'Administrative recovery permissions are fixed' using errcode='22023';
  end if;
  perform pg_advisory_xact_lock(hashtextextended(cid::text || target_role::text || wanted::text, 0));
  select exists(select 1 from public.role_permissions where clinic_id=cid and role=target_role and permission=wanted) into was_enabled;
  if enabled then
    insert into public.role_permissions values(cid,target_role,wanted) on conflict do nothing;
  else
    delete from public.role_permissions where clinic_id=cid and role=target_role and permission=wanted;
  end if;
  if was_enabled is distinct from enabled then
    insert into public.permission_audit(clinic_id,actor_id,target,action,before_value,after_value)
    values(cid,auth.uid(),target_role::text || ':' || wanted::text,'role_permission',to_jsonb(was_enabled),to_jsonb(enabled));
  end if;
end;
$$;
create function public.set_member_role(cid uuid, member_id uuid, new_role public.clinic_role) returns void
language plpgsql security definer set search_path = '' as $$
declare old_role public.clinic_role;
begin
  if not public.has_permission(cid,'roles.manage') then
    raise exception 'Permission denied' using errcode='42501';
  end if;
  -- Serialize demotions so two admins cannot concurrently remove the last administrator.
  perform 1 from public.clinics where id=cid for update;
  select role into old_role from public.memberships where clinic_id=cid and user_id=member_id for update;
  if old_role is null then raise exception 'Member not found' using errcode='P0002'; end if;
  if old_role='admin' and new_role<>'admin' and
    (select count(*) from public.memberships where clinic_id=cid and role='admin')=1 then
    raise exception 'Cannot remove last administrator' using errcode='22023';
  end if;
  update public.memberships set role=new_role where clinic_id=cid and user_id=member_id;
  if old_role is distinct from new_role then
    insert into public.permission_audit(clinic_id,actor_id,target,action,before_value,after_value)
    values(cid,auth.uid(),member_id::text,'member_role',to_jsonb(old_role),to_jsonb(new_role));
  end if;
end;
$$;
-- Explicitly remove PostgreSQL's default PUBLIC execution privilege.
revoke all on all functions in schema public from public, anon;
revoke all on all functions in schema private from public, anon;
grant execute on function public.has_permission(uuid,public.clinic_permission),
  public.set_role_permission(uuid,public.clinic_role,public.clinic_permission,boolean),
  public.set_member_role(uuid,uuid,public.clinic_role) to authenticated;
grant execute on all functions in schema private to authenticated;
alter table public.clinics enable row level security;
alter table public.memberships enable row level security;
alter table public.role_permissions enable row level security;
alter table public.patients enable row level security;
alter table public.notes enable row level security;
alter table public.appointments enable row level security;
alter table public.permission_audit enable row level security;
revoke all on all tables in schema public from anon, authenticated;
grant select on all tables in schema public to authenticated;
grant insert on public.notes to authenticated;
grant update(body) on public.notes to authenticated;
grant update(status) on public.appointments to authenticated;
create policy clinic_member on public.clinics for select to authenticated using(private.member_role(id) is not null);
create policy membership_read on public.memberships for select to authenticated using(user_id=auth.uid() or public.has_permission(clinic_id,'roles.manage'));
create policy permission_read on public.role_permissions for select to authenticated using(private.member_role(clinic_id) is not null);
create policy patient_read on public.patients for select to authenticated using(
  public.has_permission(clinic_id,'patients.read') and private.can_reach_patient(clinic_id,id));
create policy note_read on public.notes for select to authenticated using(
  public.has_permission(clinic_id,'notes.read') and private.can_reach_patient(clinic_id,patient_id));
create policy note_insert on public.notes for insert to authenticated with check(
  public.has_permission(clinic_id,'notes.write') and author_id=auth.uid() and private.can_reach_patient(clinic_id,patient_id));
create policy note_update on public.notes for update to authenticated using(
  public.has_permission(clinic_id,'notes.write') and private.can_reach_patient(clinic_id,patient_id))
  with check(public.has_permission(clinic_id,'notes.write') and private.can_reach_patient(clinic_id,patient_id));
create policy appointment_read on public.appointments for select to authenticated using(
  public.has_permission(clinic_id,'appointments.read') and private.can_reach_patient(clinic_id,patient_id));
create policy appointment_update on public.appointments for update to authenticated using(
  public.has_permission(clinic_id,'appointments.write') and private.can_reach_patient(clinic_id,patient_id))
  with check(public.has_permission(clinic_id,'appointments.write') and private.can_reach_patient(clinic_id,patient_id));
create policy audit_read on public.permission_audit for select to authenticated using(public.has_permission(clinic_id,'audit.read'));
