-- seed_v2.sql -- multi-asset rows for the 5 demo clients in seed.sql.
-- Run AFTER seed.sql.
--
-- Client UUIDs are pulled from the live Supabase project (qkydgmingqpiqzxcuqpn):
--   c1 (Aggressive)    = Rajesh Mehta   d62e9583-9d56-4e45-8665-e0634b3db42a
--   c2 (Balanced)      = Priya Iyer     e46486d4-f0b6-41ff-b9c0-b71f85223cd0
--   c3 (Conservative)  = Arjun Kapoor   410834b9-7681-4b3d-9c86-0bcbfc3e78ec
--   c4 (HNI)           = Sunita Rao     a5ab55c8-e369-4e9f-9319-a82df9214707
--   c5 (Retiree)       = Vikram Shah    5c406920-94e7-46eb-a165-7540ee608bfd

-- Support: G-Sec yield curve --------------------------------------------------
insert into market_yields (curve, tenor_years, yield_pct, as_of_date) values
  ('gsec', 1, 6.85, current_date),
  ('gsec', 3, 7.05, current_date),
  ('gsec', 5, 7.15, current_date),
  ('gsec', 10, 7.25, current_date),
  ('gsec', 30, 7.40, current_date)
on conflict (curve, tenor_years) do update
  set yield_pct = excluded.yield_pct, as_of_date = excluded.as_of_date;

-- Support: gold price seed ----------------------------------------------------
insert into gold_price_cache (purity, price_per_gram, source, fetched_at)
values ('999', 7234.50, 'ibja-seed', now());

-- Client 1 (Aggressive) -- Rajesh Mehta ---------------------------------------
insert into mutual_funds
  (client_id, scheme_code, scheme_name, amc, category, sub_category,
   units, purchase_nav, purchase_date)
values
  ('d62e9583-9d56-4e45-8665-e0634b3db42a', '125354', 'Nippon Small Cap Direct Growth',
   'Nippon India MF', 'equity', 'smallcap', 500.0, 110.50, '2023-06-15'),
  ('d62e9583-9d56-4e45-8665-e0634b3db42a', '120601', 'ICICI Value Discovery Direct Growth',
   'ICICI Prudential MF', 'equity', 'value', 800.0, 60.20, '2022-11-01');

insert into gold_holdings
  (client_id, form, weight_grams, purity,
   purchase_price_per_gram, purchase_date)
values
  ('d62e9583-9d56-4e45-8665-e0634b3db42a', 'physical', 50.0, '999', 5800.00, '2023-08-20');

insert into cash_balances (client_id, account_type, bank, balance) values
  ('d62e9583-9d56-4e45-8665-e0634b3db42a', 'savings', 'HDFC Bank', 350000);

-- Client 2 (Balanced) -- Priya Iyer -------------------------------------------
insert into mutual_funds
  (client_id, scheme_code, scheme_name, amc, category, sub_category,
   units, purchase_nav, purchase_date)
values
  ('e46486d4-f0b6-41ff-b9c0-b71f85223cd0', '120503', 'ICICI Bluechip Direct Growth',
   'ICICI Prudential MF', 'equity', 'largecap', 1200.0, 80.10, '2022-04-10'),
  ('e46486d4-f0b6-41ff-b9c0-b71f85223cd0', '118989', 'HDFC Mid Cap Opportunities Direct',
   'HDFC MF', 'equity', 'midcap', 600.0, 95.00, '2023-01-20'),
  ('e46486d4-f0b6-41ff-b9c0-b71f85223cd0', '119551', 'Axis Short Term Direct Growth',
   'Axis MF', 'debt', 'short-duration', 2000.0, 28.40, '2024-02-15');

insert into bonds
  (client_id, isin, issuer, bond_type, face_value, units,
   coupon_pct, payment_frequency, purchase_price, maturity_date,
   credit_rating, credit_spread_bps, purchase_date)
values
  ('e46486d4-f0b6-41ff-b9c0-b71f85223cd0', 'IN0020220068', 'Govt of India', 'gsec',
   1000.0, 50, 7.10, 2, 990.00, '2032-04-08', 'SOV', 0, '2023-05-12');

insert into liabilities
  (client_id, loan_type, lender, original_amount, rate_pct,
   tenor_months, emi, start_date)
values
  ('e46486d4-f0b6-41ff-b9c0-b71f85223cd0', 'home', 'HDFC Bank', 5000000.0, 8.5, 240,
   43391.16, '2022-07-01');

insert into insurance_policies
  (client_id, policy_type, insurer, sum_assured, premium_amount,
   premium_frequency, start_date, maturity_date)
values
  ('e46486d4-f0b6-41ff-b9c0-b71f85223cd0', 'term', 'HDFC Life', 10000000.0, 18000.0,
   'annual', '2021-09-01', '2046-09-01');

insert into cash_balances (client_id, account_type, bank, balance) values
  ('e46486d4-f0b6-41ff-b9c0-b71f85223cd0', 'savings', 'Kotak', 220000),
  ('e46486d4-f0b6-41ff-b9c0-b71f85223cd0', 'sweep', 'Kotak', 180000);

-- Client 3 (Conservative) -- Arjun Kapoor -------------------------------------
insert into mutual_funds
  (client_id, scheme_code, scheme_name, amc, category, sub_category,
   units, purchase_nav, purchase_date)
values
  ('410834b9-7681-4b3d-9c86-0bcbfc3e78ec', '119551', 'Axis Short Term Direct Growth',
   'Axis MF', 'debt', 'short-duration', 5000.0, 27.10, '2022-08-01'),
  ('410834b9-7681-4b3d-9c86-0bcbfc3e78ec', '120466', 'SBI Magnum Gilt Direct Growth',
   'SBI MF', 'debt', 'gilt', 3000.0, 49.50, '2023-03-01');

insert into fixed_deposits
  (client_id, bank, principal, rate_pct, start_date, maturity_date,
   compounding)
values
  ('410834b9-7681-4b3d-9c86-0bcbfc3e78ec', 'SBI', 800000.0, 7.10, '2024-01-15',
   '2027-01-15', 'quarterly'),
  ('410834b9-7681-4b3d-9c86-0bcbfc3e78ec', 'ICICI', 500000.0, 7.25, '2023-11-01',
   '2025-11-01', 'quarterly');

insert into insurance_policies
  (client_id, policy_type, insurer, sum_assured, premium_amount,
   premium_frequency, start_date, maturity_date)
values
  ('410834b9-7681-4b3d-9c86-0bcbfc3e78ec', 'endowment', 'LIC', 1500000.0, 75000.0,
   'annual', '2018-04-15', '2038-04-15');

insert into gold_holdings
  (client_id, form, weight_grams, purity,
   purchase_price_per_gram, purchase_date)
values
  ('410834b9-7681-4b3d-9c86-0bcbfc3e78ec', 'physical', 100.0, '999', 5200.00, '2021-02-20');

insert into liabilities
  (client_id, loan_type, lender, original_amount, rate_pct,
   tenor_months, emi, start_date)
values
  ('410834b9-7681-4b3d-9c86-0bcbfc3e78ec', 'car', 'ICICI Bank', 800000.0, 9.5, 60,
   16795.0, '2023-06-01');

insert into cash_balances (client_id, account_type, bank, balance) values
  ('410834b9-7681-4b3d-9c86-0bcbfc3e78ec', 'savings', 'SBI', 450000);

-- Client 4 (HNI) -- Sunita Rao ------------------------------------------------
insert into mutual_funds
  (client_id, scheme_code, scheme_name, amc, category, sub_category,
   units, purchase_nav, purchase_date)
values
  ('a5ab55c8-e369-4e9f-9319-a82df9214707', '120503', 'ICICI Bluechip Direct Growth',
   'ICICI Prudential MF', 'equity', 'largecap', 3000.0, 75.00, '2020-09-12'),
  ('a5ab55c8-e369-4e9f-9319-a82df9214707', '120466', 'SBI Magnum Gilt Direct Growth',
   'SBI MF', 'debt', 'gilt', 8000.0, 47.20, '2022-06-01'),
  ('a5ab55c8-e369-4e9f-9319-a82df9214707', '118989', 'HDFC Mid Cap Opportunities Direct',
   'HDFC MF', 'equity', 'midcap', 1500.0, 92.30, '2021-11-15'),
  ('a5ab55c8-e369-4e9f-9319-a82df9214707', '125354', 'Nippon Small Cap Direct Growth',
   'Nippon India MF', 'equity', 'smallcap', 600.0, 105.40, '2022-03-20'),
  ('a5ab55c8-e369-4e9f-9319-a82df9214707', '119551', 'Axis Short Term Direct Growth',
   'Axis MF', 'debt', 'short-duration', 4000.0, 28.10, '2023-09-01');

insert into bonds
  (client_id, isin, issuer, bond_type, face_value, units, coupon_pct,
   payment_frequency, purchase_price, maturity_date, credit_rating,
   credit_spread_bps, purchase_date)
values
  ('a5ab55c8-e369-4e9f-9319-a82df9214707', 'INE001A07TQ4', 'HDFC Ltd', 'corporate',
   1000.0, 200, 8.20, 1, 1005.0, '2029-12-15', 'AAA', 50, '2022-12-10'),
  ('a5ab55c8-e369-4e9f-9319-a82df9214707', 'INE020B08DM5', 'REC Ltd', 'corporate',
   1000.0, 150, 7.85, 2, 998.0, '2031-05-20', 'AAA', 60, '2023-04-22');

insert into fixed_deposits
  (client_id, bank, principal, rate_pct, start_date, maturity_date,
   compounding)
values
  ('a5ab55c8-e369-4e9f-9319-a82df9214707', 'HDFC', 1500000.0, 7.50, '2024-03-01',
   '2027-03-01', 'quarterly'),
  ('a5ab55c8-e369-4e9f-9319-a82df9214707', 'Kotak', 1000000.0, 7.40, '2023-12-15',
   '2026-12-15', 'monthly');

insert into insurance_policies
  (client_id, policy_type, insurer, sum_assured, premium_amount,
   premium_frequency, start_date, maturity_date)
values
  ('a5ab55c8-e369-4e9f-9319-a82df9214707', 'ulip', 'ICICI Pru', 5000000.0, 200000.0,
   'annual', '2019-08-10', '2034-08-10');

insert into gold_holdings
  (client_id, form, weight_grams, purity,
   purchase_price_per_gram, purchase_date)
values
  ('a5ab55c8-e369-4e9f-9319-a82df9214707', 'sgb', 200.0, '999', 5450.00, '2022-05-30');

insert into cash_balances (client_id, account_type, bank, balance) values
  ('a5ab55c8-e369-4e9f-9319-a82df9214707', 'savings', 'HDFC Bank', 850000),
  ('a5ab55c8-e369-4e9f-9319-a82df9214707', 'sweep', 'HDFC Bank', 1200000);

-- Client 5 (Retiree) -- Vikram Shah -------------------------------------------
insert into mutual_funds
  (client_id, scheme_code, scheme_name, amc, category, sub_category,
   units, purchase_nav, purchase_date)
values
  ('5c406920-94e7-46eb-a165-7540ee608bfd', '120601', 'ICICI Value Discovery Direct Growth',
   'ICICI Prudential MF', 'equity', 'value', 400.0, 58.10, '2021-04-12'),
  ('5c406920-94e7-46eb-a165-7540ee608bfd', '120466', 'SBI Magnum Gilt Direct Growth',
   'SBI MF', 'debt', 'gilt', 4000.0, 46.80, '2022-01-15'),
  ('5c406920-94e7-46eb-a165-7540ee608bfd', '119551', 'Axis Short Term Direct Growth',
   'Axis MF', 'debt', 'short-duration', 3000.0, 27.40, '2023-02-20');

insert into fixed_deposits
  (client_id, bank, principal, rate_pct, start_date, maturity_date,
   compounding)
values
  ('5c406920-94e7-46eb-a165-7540ee608bfd', 'SBI', 1200000.0, 7.75, '2024-06-01',
   '2027-06-01', 'quarterly'),
  ('5c406920-94e7-46eb-a165-7540ee608bfd', 'SBI', 800000.0, 7.50, '2023-09-10',
   '2026-09-10', 'quarterly'),
  ('5c406920-94e7-46eb-a165-7540ee608bfd', 'PNB', 600000.0, 8.00, '2024-02-15',
   '2029-02-15', 'quarterly');

insert into insurance_policies
  (client_id, policy_type, insurer, sum_assured, premium_amount,
   premium_frequency, start_date, maturity_date)
values
  ('5c406920-94e7-46eb-a165-7540ee608bfd', 'annuity', 'LIC', 2000000.0, 10000.0,
   'monthly', '2019-01-15', '2039-01-15');

insert into cash_balances (client_id, account_type, bank, balance) values
  ('5c406920-94e7-46eb-a165-7540ee608bfd', 'savings', 'SBI', 150000);
