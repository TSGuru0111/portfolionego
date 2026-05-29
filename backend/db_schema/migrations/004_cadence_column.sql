-- 004_cadence_column.sql
ALTER TABLE reports
  ADD COLUMN cadence text NOT NULL DEFAULT 'monthly'
    CHECK (cadence IN ('weekly', 'monthly', 'quarterly'));

CREATE INDEX reports_cadence_created_idx
  ON reports(cadence, created_at DESC);
