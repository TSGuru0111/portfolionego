-- Phase 2: change-tracking model
-- Adds wealth_snapshots, allocation_targets, rationale_events + RLS;
-- extends transactions with rationale_event_id.

-- rationale_events first (other tables FK to it). Back-FKs added after the
-- other tables exist (snapshot_id, linked_target_id).
create table rationale_events (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references clients(id) on delete cascade,
  event_date timestamptz not null,
  event_type text not null check (event_type in (
    'target_change','rebalance','cash_deployment','tax_harvest',
    'liquidity_event','external_change','market_commentary','onboarding'
  )),
  title text not null check (char_length(title) <= 200),
  rationale_text text not null,
  snapshot_id uuid null,
  linked_target_id uuid null,
  created_by_rm_id uuid not null references rms(id),
  created_at timestamptz not null default now()
);
create index rationale_events_client_date_idx
  on rationale_events(client_id, event_date desc);
create index rationale_events_client_type_idx
  on rationale_events(client_id, event_type, event_date desc);

create table wealth_snapshots (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references clients(id) on delete cascade,
  as_of timestamptz not null,
  trigger text not null check (trigger in ('report','rationale','monthly')),
  rationale_event_id uuid null references rationale_events(id),
  report_id uuid null references reports(id),

  net_worth numeric(18,2) not null,
  total_assets numeric(18,2) not null,
  total_liabilities numeric(18,2) not null,
  total_unrealised_gain numeric(18,2) not null,
  allocation_pct jsonb not null,

  snapshot_json jsonb not null,

  has_stale_values boolean not null default false,
  stale_sources text[] not null default '{}',

  created_at timestamptz not null default now()
);
create index wealth_snapshots_client_asof_idx
  on wealth_snapshots(client_id, as_of desc);
create index wealth_snapshots_client_trigger_idx
  on wealth_snapshots(client_id, trigger, as_of desc);

create table allocation_targets (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references clients(id) on delete cascade,
  effective_from timestamptz not null,
  effective_to timestamptz null,

  equity_pct numeric(5,2) not null check (equity_pct between 0 and 100),
  debt_pct numeric(5,2) not null check (debt_pct between 0 and 100),
  gold_pct numeric(5,2) not null check (gold_pct between 0 and 100),
  cash_pct numeric(5,2) not null check (cash_pct between 0 and 100),
  alternatives_pct numeric(5,2) not null check (alternatives_pct between 0 and 100),
  check (round((equity_pct + debt_pct + gold_pct + cash_pct + alternatives_pct)::numeric, 2) = 100),

  equity_band_pct numeric(5,2) not null default 5,
  debt_band_pct numeric(5,2) not null default 5,
  gold_band_pct numeric(5,2) not null default 2,
  cash_band_pct numeric(5,2) not null default 3,
  alternatives_band_pct numeric(5,2) not null default 3,

  rationale_event_id uuid not null references rationale_events(id),
  created_by_rm_id uuid not null references rms(id),
  created_at timestamptz not null default now()
);
create unique index allocation_targets_one_active_per_client
  on allocation_targets(client_id) where effective_to is null;
create index allocation_targets_client_history_idx
  on allocation_targets(client_id, effective_from desc);

-- Back-FKs from rationale_events
alter table rationale_events
  add constraint rationale_events_snapshot_fk
    foreign key (snapshot_id) references wealth_snapshots(id);
alter table rationale_events
  add constraint rationale_events_linked_target_fk
    foreign key (linked_target_id) references allocation_targets(id);

alter table transactions
  add column rationale_event_id uuid null references rationale_events(id);

-- RLS
alter table rationale_events enable row level security;
create policy "RM owns rationale_events via client"
  on rationale_events for all
  using (exists (
    select 1 from clients c
    where c.id = rationale_events.client_id and c.rm_id = auth.uid()
  ));

alter table wealth_snapshots enable row level security;
create policy "RM owns wealth_snapshots via client"
  on wealth_snapshots for all
  using (exists (
    select 1 from clients c
    where c.id = wealth_snapshots.client_id and c.rm_id = auth.uid()
  ));

alter table allocation_targets enable row level security;
create policy "RM owns allocation_targets via client"
  on allocation_targets for all
  using (exists (
    select 1 from clients c
    where c.id = allocation_targets.client_id and c.rm_id = auth.uid()
  ));
