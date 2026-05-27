-- Atomic allocation-target change.
-- Stamps prior active row's effective_to to now() and inserts a new active row
-- in one transaction. Returns the new row's id.

create or replace function change_allocation_target(
  p_client_id uuid,
  p_rationale_event_id uuid,
  p_rm_id uuid,
  p_equity_pct numeric,
  p_debt_pct numeric,
  p_gold_pct numeric,
  p_cash_pct numeric,
  p_alternatives_pct numeric,
  p_equity_band_pct numeric,
  p_debt_band_pct numeric,
  p_gold_band_pct numeric,
  p_cash_band_pct numeric,
  p_alternatives_band_pct numeric
) returns uuid
language plpgsql
security definer
as $$
declare
  new_id uuid;
  now_ts timestamptz := now();
begin
  update allocation_targets
    set effective_to = now_ts
    where client_id = p_client_id and effective_to is null;

  insert into allocation_targets (
    client_id, effective_from, effective_to,
    equity_pct, debt_pct, gold_pct, cash_pct, alternatives_pct,
    equity_band_pct, debt_band_pct, gold_band_pct, cash_band_pct, alternatives_band_pct,
    rationale_event_id, created_by_rm_id
  ) values (
    p_client_id, now_ts, null,
    p_equity_pct, p_debt_pct, p_gold_pct, p_cash_pct, p_alternatives_pct,
    p_equity_band_pct, p_debt_band_pct, p_gold_band_pct, p_cash_band_pct, p_alternatives_band_pct,
    p_rationale_event_id, p_rm_id
  )
  returning id into new_id;

  return new_id;
end;
$$;
