-- backend/db_schema/migrations/001_qa_reasons.sql
-- Adds qa_reasons JSONB column to reports for QA-badge transparency.
-- Additive only — safe on existing data.

alter table reports
  add column if not exists qa_reasons jsonb default '[]'::jsonb;

comment on column reports.qa_reasons is
  'Array of short strings from the Cohere QA grader explaining the score.';
