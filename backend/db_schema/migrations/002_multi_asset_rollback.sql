-- Rollback for 002_multi_asset.sql. Drops in reverse dependency order.
begin;
drop table if exists gold_price_cache cascade;
drop table if exists nav_cache cascade;
drop table if exists market_yields cascade;
drop table if exists liabilities cascade;
drop table if exists insurance_policies cascade;
drop table if exists fixed_deposits cascade;
drop table if exists cash_balances cascade;
drop table if exists gold_holdings cascade;
drop table if exists bonds cascade;
drop table if exists mutual_funds cascade;
commit;
