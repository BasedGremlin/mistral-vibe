-- Applied to Supabase project dxyghtyjndylvfugutsr on 2026-07-16.
-- Retained here for local review and reproducibility.

create schema if not exists control;

do $$ begin
  if exists (
    select 1 from pg_constraint
    where conrelid = 'public.connector_outbox'::regclass
      and conname = 'connector_outbox_target_check'
  ) then
    alter table public.connector_outbox
      drop constraint connector_outbox_target_check;
  end if;
end $$;

alter table public.connector_outbox
  add constraint connector_outbox_target_check
  check (target = any (array[
    'supabase'::text,
    'asana'::text,
    'github'::text,
    'vercel'::text,
    'notion'::text,
    'linear'::text,
    'openai'::text,
    'anthropic'::text,
    'huggingface'::text,
    'canva'::text
  ]));

create table if not exists control.swarm_runs (
  run_id uuid primary key default gen_random_uuid(),
  external_swarm_id bigint,
  owner_ref text,
  query text not null,
  provider_plan jsonb not null default '{}'::jsonb,
  status text not null default 'created'
    check (status in ('created','running','paused','completed','failed')),
  current_state text not null default 'INTAKE'
    check (current_state in (
      'INTAKE','PLAN','ROUTE','EXECUTE','CRITIQUE',
      'VALIDATE','PERSIST','COMPLETE','FAILED'
    )),
  final_summary text,
  error_code text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz
);

create table if not exists control.swarm_events (
  event_id bigint generated always as identity primary key,
  run_id uuid not null references control.swarm_runs(run_id) on delete cascade,
  event_type text not null,
  agent_slug text,
  state text,
  payload jsonb not null default '{}'::jsonb,
  occurred_at timestamptz not null default now()
);

create table if not exists control.swarm_checkpoints (
  checkpoint_id bigint generated always as identity primary key,
  run_id uuid not null references control.swarm_runs(run_id) on delete cascade,
  agent_slug text not null,
  sequence_no integer not null,
  checksum text not null,
  snapshot jsonb not null,
  created_at timestamptz not null default now(),
  unique (run_id, agent_slug, sequence_no)
);

create index if not exists idx_swarm_runs_status
  on control.swarm_runs(status, updated_at desc);
create index if not exists idx_swarm_events_run
  on control.swarm_events(run_id, event_id);
create index if not exists idx_swarm_checkpoints_run
  on control.swarm_checkpoints(run_id, sequence_no);

alter table control.swarm_runs enable row level security;
alter table control.swarm_events enable row level security;
alter table control.swarm_checkpoints enable row level security;

grant usage on schema control to service_role;
grant all on control.swarm_runs, control.swarm_events, control.swarm_checkpoints
  to service_role;
grant usage, select on all sequences in schema control to service_role;

-- RPC bridge: control schema stays unexposed; only service_role may execute.
create or replace function public.swarm_create_run(
  p_external_swarm_id bigint,
  p_owner_ref text,
  p_query text,
  p_provider_plan jsonb
) returns uuid
language plpgsql
security definer
set search_path = control, public, pg_temp
as $$
declare v_run_id uuid;
begin
  insert into control.swarm_runs (
    external_swarm_id, owner_ref, query, provider_plan, status, current_state
  ) values (
    p_external_swarm_id, p_owner_ref, p_query, coalesce(p_provider_plan, '{}'::jsonb), 'running', 'INTAKE'
  ) returning run_id into v_run_id;
  return v_run_id;
end;
$$;

create or replace function public.swarm_append_event(
  p_run_id uuid,
  p_event_type text,
  p_state text,
  p_agent_slug text default null,
  p_payload jsonb default '{}'::jsonb
) returns void
language plpgsql
security definer
set search_path = control, public, pg_temp
as $$
begin
  insert into control.swarm_events(run_id, event_type, agent_slug, state, payload)
  values (p_run_id, p_event_type, p_agent_slug, p_state, coalesce(p_payload, '{}'::jsonb));

  update control.swarm_runs
  set current_state = p_state, updated_at = now()
  where run_id = p_run_id;
end;
$$;

create or replace function public.swarm_write_checkpoint(
  p_run_id uuid,
  p_agent_slug text,
  p_sequence_no integer,
  p_checksum text,
  p_snapshot jsonb
) returns void
language plpgsql
security definer
set search_path = control, public, pg_temp
as $$
begin
  insert into control.swarm_checkpoints(
    run_id, agent_slug, sequence_no, checksum, snapshot
  ) values (
    p_run_id, p_agent_slug, p_sequence_no, p_checksum, p_snapshot
  )
  on conflict (run_id, agent_slug, sequence_no)
  do update set checksum = excluded.checksum,
                snapshot = excluded.snapshot,
                created_at = now();
end;
$$;

create or replace function public.swarm_complete_run(
  p_run_id uuid,
  p_final_summary text default null,
  p_failed boolean default false,
  p_error_code text default null
) returns void
language plpgsql
security definer
set search_path = control, public, pg_temp
as $$
begin
  update control.swarm_runs
  set status = case when p_failed then 'failed' else 'completed' end,
      current_state = case when p_failed then 'FAILED' else 'COMPLETE' end,
      final_summary = p_final_summary,
      error_code = p_error_code,
      updated_at = now(),
      completed_at = now()
  where run_id = p_run_id;
end;
$$;

revoke all on function public.swarm_create_run(bigint,text,text,jsonb) from public, anon, authenticated;
revoke all on function public.swarm_append_event(uuid,text,text,text,jsonb) from public, anon, authenticated;
revoke all on function public.swarm_write_checkpoint(uuid,text,integer,text,jsonb) from public, anon, authenticated;
revoke all on function public.swarm_complete_run(uuid,text,boolean,text) from public, anon, authenticated;

grant execute on function public.swarm_create_run(bigint,text,text,jsonb) to service_role;
grant execute on function public.swarm_append_event(uuid,text,text,text,jsonb) to service_role;
grant execute on function public.swarm_write_checkpoint(uuid,text,integer,text,jsonb) to service_role;
grant execute on function public.swarm_complete_run(uuid,text,boolean,text) to service_role;
