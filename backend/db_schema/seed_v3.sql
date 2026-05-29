-- seed_v3.sql — Phase 2 demo seed.
-- Run AFTER seed_v2.sql.
-- Required psql variable: :rm_id (the RM user UUID who owns the demo clients).
--
-- Usage:
--   psql "$DATABASE_URL" -v rm_id="'YOUR-RM-UUID-HERE'" \
--        -f backend/db_schema/seed_v3.sql
--
-- After this script, run a one-time seed of monthly snapshots:
--   curl -X POST "$BACKEND_URL/jobs/monthly-snapshots?secret=$JOB_SECRET"
--
-- Demo clients (from seed_v2.sql):
--   c1 Rajesh Mehta    d62e9583-9d56-4e45-8665-e0634b3db42a  Aggressive
--   c2 Priya Iyer      e46486d4-f0b6-41ff-b9c0-b71f85223cd0  Moderate
--   c3 Arjun Kapoor    410834b9-7681-4b3d-9c86-0bcbfc3e78ec  Moderate
--   c4 Sunita Rao      a5ab55c8-e369-4e9f-9319-a82df9214707  Aggressive
--   c5 Vikram Shah     5c406920-94e7-46eb-a165-7540ee608bfd  Conservative

BEGIN;

-- ---------------------------------------------------------------
-- Rajesh Mehta — Aggressive (d62e9583-...)
-- ---------------------------------------------------------------
WITH e AS (
  INSERT INTO rationale_events
    (client_id, event_type, event_date, title, rationale_text, created_by_rm_id)
  VALUES
    ('d62e9583-9d56-4e45-8665-e0634b3db42a',
     'onboarding',
     '2024-01-15',
     'Initial onboarding',
     'Risk profile Aggressive — high equity tilt, 7+ year horizon, comfortable with volatility.',
     :rm_id)
  RETURNING id
)
INSERT INTO allocation_targets
  (client_id, effective_from,
   equity_pct, debt_pct, gold_pct, cash_pct, alternatives_pct,
   equity_band_pct, debt_band_pct, gold_band_pct, cash_band_pct, alternatives_band_pct,
   rationale_event_id, created_by_rm_id)
SELECT
  'd62e9583-9d56-4e45-8665-e0634b3db42a',
  '2024-01-15',
  65, 20, 5, 8, 2,
  5, 5, 2, 3, 3,
  e.id, :rm_id
FROM e;

-- ---------------------------------------------------------------
-- Priya Iyer — Moderate (e46486d4-...)
-- ---------------------------------------------------------------
WITH e AS (
  INSERT INTO rationale_events
    (client_id, event_type, event_date, title, rationale_text, created_by_rm_id)
  VALUES
    ('e46486d4-f0b6-41ff-b9c0-b71f85223cd0',
     'onboarding',
     '2024-02-01',
     'Initial onboarding',
     'Risk profile Moderate — balanced growth and stability, 5-7 year horizon.',
     :rm_id)
  RETURNING id
)
INSERT INTO allocation_targets
  (client_id, effective_from,
   equity_pct, debt_pct, gold_pct, cash_pct, alternatives_pct,
   equity_band_pct, debt_band_pct, gold_band_pct, cash_band_pct, alternatives_band_pct,
   rationale_event_id, created_by_rm_id)
SELECT
  'e46486d4-f0b6-41ff-b9c0-b71f85223cd0',
  '2024-02-01',
  45, 35, 8, 10, 2,
  5, 5, 2, 3, 3,
  e.id, :rm_id
FROM e;

-- ---------------------------------------------------------------
-- Arjun Kapoor — Moderate (410834b9-...)
-- ---------------------------------------------------------------
WITH e AS (
  INSERT INTO rationale_events
    (client_id, event_type, event_date, title, rationale_text, created_by_rm_id)
  VALUES
    ('410834b9-7681-4b3d-9c86-0bcbfc3e78ec',
     'onboarding',
     '2024-03-10',
     'Initial onboarding',
     'Risk profile Moderate — balanced growth approach, medium-term horizon.',
     :rm_id)
  RETURNING id
)
INSERT INTO allocation_targets
  (client_id, effective_from,
   equity_pct, debt_pct, gold_pct, cash_pct, alternatives_pct,
   equity_band_pct, debt_band_pct, gold_band_pct, cash_band_pct, alternatives_band_pct,
   rationale_event_id, created_by_rm_id)
SELECT
  '410834b9-7681-4b3d-9c86-0bcbfc3e78ec',
  '2024-03-10',
  45, 35, 8, 10, 2,
  5, 5, 2, 3, 3,
  e.id, :rm_id
FROM e;

-- ---------------------------------------------------------------
-- Sunita Rao — Aggressive (a5ab55c8-...)
-- ---------------------------------------------------------------
WITH e AS (
  INSERT INTO rationale_events
    (client_id, event_type, event_date, title, rationale_text, created_by_rm_id)
  VALUES
    ('a5ab55c8-e369-4e9f-9319-a82df9214707',
     'onboarding',
     '2024-04-05',
     'Initial onboarding',
     'Risk profile Aggressive — HNI client, long time horizon, growth focused.',
     :rm_id)
  RETURNING id
)
INSERT INTO allocation_targets
  (client_id, effective_from,
   equity_pct, debt_pct, gold_pct, cash_pct, alternatives_pct,
   equity_band_pct, debt_band_pct, gold_band_pct, cash_band_pct, alternatives_band_pct,
   rationale_event_id, created_by_rm_id)
SELECT
  'a5ab55c8-e369-4e9f-9319-a82df9214707',
  '2024-04-05',
  65, 20, 5, 8, 2,
  5, 5, 2, 3, 3,
  e.id, :rm_id
FROM e;

-- ---------------------------------------------------------------
-- Vikram Shah — Conservative (5c406920-...)
-- ---------------------------------------------------------------
WITH e AS (
  INSERT INTO rationale_events
    (client_id, event_type, event_date, title, rationale_text, created_by_rm_id)
  VALUES
    ('5c406920-94e7-46eb-a165-7540ee608bfd',
     'onboarding',
     '2024-05-20',
     'Initial onboarding',
     'Risk profile Conservative — retiree, capital preservation and income focus.',
     :rm_id)
  RETURNING id
)
INSERT INTO allocation_targets
  (client_id, effective_from,
   equity_pct, debt_pct, gold_pct, cash_pct, alternatives_pct,
   equity_band_pct, debt_band_pct, gold_band_pct, cash_band_pct, alternatives_band_pct,
   rationale_event_id, created_by_rm_id)
SELECT
  '5c406920-94e7-46eb-a165-7540ee608bfd',
  '2024-05-20',
  25, 55, 8, 10, 2,
  5, 5, 2, 3, 3,
  e.id, :rm_id
FROM e;

COMMIT;
