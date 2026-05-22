-- PortfolioNarrator — synthetic seed data (5 HNI clients).
-- Run after schema.sql and rls.sql.
--
-- Uses a CTE so we can capture the new RM id without manual edits.

with rm as (
    insert into rms (email, name, firm_name, designation, phone)
    values (
        'priya@wealthfirm.com',
        'Priya Sharma',
        'Kotak Private Banking',
        'Senior Relationship Manager',
        '+91 98765 43210'
    )
    returning id
),

-- ─── 5 HNI clients ────────────────────────────────────────────────────
c1 as (
    insert into clients (
        rm_id, name, aum_cr, risk_profile, investment_horizon,
        liquidity_need_pct, tax_bracket, language_pref, tone_pref,
        client_since, next_review_date, last_meeting_notes,
        rm_email, rm_phone
    )
    select id, 'Rajesh Mehta', 2.50, 'moderate', '5yr',
           15.0, '30%', 'english', 'warm',
           '2023-04-01', '2026-05-15',
           'Client happy with IT allocation. Wants to explore gold.',
           'priya@wealthfirm.com', '+91 98765 43210'
    from rm
    returning id
),
c2 as (
    insert into clients (
        rm_id, name, aum_cr, risk_profile, investment_horizon,
        liquidity_need_pct, tax_bracket, language_pref, tone_pref,
        client_since, next_review_date, last_meeting_notes,
        rm_email, rm_phone
    )
    select id, 'Priya Iyer', 1.20, 'aggressive', '3yr',
           10.0, '30%', 'english', 'formal',
           '2024-01-15', '2026-06-01',
           'Concerned about IT underperformance. Discussed diversification.',
           'priya@wealthfirm.com', '+91 98765 43210'
    from rm
    returning id
),
c3 as (
    insert into clients (
        rm_id, name, aum_cr, risk_profile, investment_horizon,
        liquidity_need_pct, tax_bracket, language_pref, tone_pref,
        client_since, next_review_date,
        rm_email, rm_phone
    )
    select id, 'Arjun Kapoor', 5.00, 'moderate', 'long_term',
           20.0, 'HUF', 'english', 'warm',
           '2022-07-01', '2026-05-20',
           'priya@wealthfirm.com', '+91 98765 43210'
    from rm
    returning id
),
c4 as (
    insert into clients (
        rm_id, name, aum_cr, risk_profile, investment_horizon,
        liquidity_need_pct, income_need_monthly, tax_bracket,
        language_pref, tone_pref, client_since,
        rm_email, rm_phone
    )
    select id, 'Sunita Rao', 0.75, 'conservative', '3yr',
           30.0, 25000, '20%',
           'hindi', 'formal', '2024-06-01',
           'priya@wealthfirm.com', '+91 98765 43210'
    from rm
    returning id
),
c5 as (
    insert into clients (
        rm_id, name, aum_cr, risk_profile, investment_horizon,
        liquidity_need_pct, tax_bracket, language_pref, tone_pref,
        client_since, next_review_date, last_meeting_notes,
        rm_email, rm_phone
    )
    select id, 'Vikram Shah', 8.00, 'aggressive', 'long_term',
           5.0, '30%', 'english', 'concise',
           '2021-01-01', '2026-05-25',
           'Interested in AIF exposure. Discussed US market risk.',
           'priya@wealthfirm.com', '+91 98765 43210'
    from rm
    returning id
),

-- ─── Portfolios (one per client, NSE tickers + ISIN) ──────────────────
p1 as (
    insert into portfolios (client_id, holdings, benchmark, inception_date)
    select id, '[
        {"ticker":"TCS","company_name":"Tata Consultancy Services","isin":"INE467B01029","qty":50,"buy_price":3200,"sector":"IT","asset_class":"equity","buy_date":"2025-01-15"},
        {"ticker":"INFY","company_name":"Infosys","isin":"INE009A01021","qty":60,"buy_price":1480,"sector":"IT","asset_class":"equity","buy_date":"2024-11-10"},
        {"ticker":"HDFCBANK","company_name":"HDFC Bank","isin":"INE040A01034","qty":80,"buy_price":1620,"sector":"BFSI","asset_class":"equity","buy_date":"2024-08-22"},
        {"ticker":"ICICIBANK","company_name":"ICICI Bank","isin":"INE090A01021","qty":70,"buy_price":1080,"sector":"BFSI","asset_class":"equity","buy_date":"2024-09-05"}
    ]'::jsonb, 'NIFTY50', '2023-04-01'
    from c1
    returning client_id
),
p2 as (
    insert into portfolios (client_id, holdings, benchmark, inception_date)
    select id, '[
        {"ticker":"TCS","company_name":"Tata Consultancy Services","isin":"INE467B01029","qty":30,"buy_price":3400,"sector":"IT","asset_class":"equity","buy_date":"2024-03-12"},
        {"ticker":"WIPRO","company_name":"Wipro","isin":"INE075A01022","qty":200,"buy_price":520,"sector":"IT","asset_class":"equity","buy_date":"2024-05-20"},
        {"ticker":"PAYTM","company_name":"One 97 Communications","isin":"INE982J01020","qty":150,"buy_price":850,"sector":"Fintech","asset_class":"equity","buy_date":"2024-02-08"}
    ]'::jsonb, 'NIFTY50', '2024-01-15'
    from c2
    returning client_id
),
p3 as (
    insert into portfolios (client_id, holdings, benchmark, inception_date)
    select id, '[
        {"ticker":"RELIANCE","company_name":"Reliance Industries","isin":"INE002A01018","qty":100,"buy_price":2500,"sector":"Energy","asset_class":"equity","buy_date":"2022-08-10"},
        {"ticker":"HDFCBANK","company_name":"HDFC Bank","isin":"INE040A01034","qty":120,"buy_price":1500,"sector":"BFSI","asset_class":"equity","buy_date":"2023-01-15"},
        {"ticker":"BHARTIARTL","company_name":"Bharti Airtel","isin":"INE397D01024","qty":150,"buy_price":920,"sector":"Telecom","asset_class":"equity","buy_date":"2023-06-30"},
        {"ticker":"ITC","company_name":"ITC","isin":"INE154A01025","qty":300,"buy_price":410,"sector":"FMCG","asset_class":"equity","buy_date":"2023-11-22"},
        {"ticker":"SUNPHARMA","company_name":"Sun Pharma","isin":"INE044A01036","qty":80,"buy_price":1170,"sector":"Pharma","asset_class":"equity","buy_date":"2024-02-18"}
    ]'::jsonb, 'NIFTY50', '2022-07-01'
    from c3
    returning client_id
),
p4 as (
    insert into portfolios (client_id, holdings, benchmark, inception_date)
    select id, '[
        {"ticker":"HDFCBANK","company_name":"HDFC Bank","isin":"INE040A01034","qty":40,"buy_price":1580,"sector":"BFSI","asset_class":"equity","buy_date":"2024-06-15"},
        {"ticker":"NESTLEIND","company_name":"Nestle India","isin":"INE239A01016","qty":15,"buy_price":2400,"sector":"FMCG","asset_class":"equity","buy_date":"2024-07-22"},
        {"ticker":"HINDUNILVR","company_name":"Hindustan Unilever","isin":"INE030A01027","qty":30,"buy_price":2280,"sector":"FMCG","asset_class":"equity","buy_date":"2024-08-05"}
    ]'::jsonb, 'NIFTY50', '2024-06-01'
    from c4
    returning client_id
),
p5 as (
    insert into portfolios (client_id, holdings, benchmark, inception_date)
    select id, '[
        {"ticker":"TCS","company_name":"Tata Consultancy Services","isin":"INE467B01029","qty":150,"buy_price":3100,"sector":"IT","asset_class":"equity","buy_date":"2023-09-12"},
        {"ticker":"INFY","company_name":"Infosys","isin":"INE009A01021","qty":200,"buy_price":1420,"sector":"IT","asset_class":"equity","buy_date":"2023-11-04"},
        {"ticker":"HDFCBANK","company_name":"HDFC Bank","isin":"INE040A01034","qty":250,"buy_price":1560,"sector":"BFSI","asset_class":"equity","buy_date":"2023-12-18"},
        {"ticker":"RELIANCE","company_name":"Reliance Industries","isin":"INE002A01018","qty":180,"buy_price":2450,"sector":"Energy","asset_class":"equity","buy_date":"2024-01-22"},
        {"ticker":"BAJFINANCE","company_name":"Bajaj Finance","isin":"INE296A01024","qty":40,"buy_price":7100,"sector":"BFSI","asset_class":"equity","buy_date":"2024-03-08"},
        {"ticker":"ASIANPAINT","company_name":"Asian Paints","isin":"INE021A01026","qty":60,"buy_price":2960,"sector":"Materials","asset_class":"equity","buy_date":"2024-04-15"},
        {"ticker":"DRREDDY","company_name":"Dr Reddy''s Laboratories","isin":"INE089A01023","qty":50,"buy_price":5400,"sector":"Pharma","asset_class":"equity","buy_date":"2024-05-20"}
    ]'::jsonb, 'NIFTY50', '2021-01-01'
    from c5
    returning client_id
)

-- ─── A few transactions per client with rationale ─────────────────────
insert into transactions
    (client_id, txn_type, ticker, isin, quantity, price, total_value, txn_date, rationale, executed_by)
select client_id, 'buy', 'TCS', 'INE467B01029', 50, 3200, 160000, '2025-01-15',
       'Added TCS on IT dip — strong deal pipeline visibility from Q3 results.',
       'Priya Sharma' from c1
union all
select client_id, 'buy', 'HDFCBANK', 'INE040A01034', 80, 1620, 129600, '2024-08-22',
       'Initiated BFSI exposure with HDFC Bank post-merger; valuations attractive.',
       'Priya Sharma' from c1
union all
select client_id, 'buy', 'INFY', 'INE009A01021', 60, 1480, 88800, '2024-11-10',
       'Topped up Infosys on margin-guidance dip; remain bullish on US discretionary recovery.',
       'Priya Sharma' from c1
union all
select client_id, 'buy', 'PAYTM', 'INE982J01020', 150, 850, 127500, '2024-02-08',
       'Tactical position in Paytm post-RBI overhang; high-risk component of the book.',
       'Priya Sharma' from c2
union all
select client_id, 'buy', 'WIPRO', 'INE075A01022', 200, 520, 104000, '2024-05-20',
       'Wipro acquisition to broaden IT mix beyond TCS — diversifies single-name risk.',
       'Priya Sharma' from c2
union all
select client_id, 'buy', 'SUNPHARMA', 'INE044A01036', 80, 1170, 93600, '2024-02-18',
       'Added pharma to balance the equity book; specialty US business performing well.',
       'Priya Sharma' from c3
union all
select client_id, 'buy', 'BHARTIARTL', 'INE397D01024', 150, 920, 138000, '2023-06-30',
       'Telecom tariff hikes thesis playing out; Airtel positioned well vs peers.',
       'Priya Sharma' from c3
union all
select client_id, 'buy', 'NESTLEIND', 'INE239A01016', 15, 2400, 36000, '2024-07-22',
       'Defensive FMCG addition for income-need profile.',
       'Priya Sharma' from c4
union all
select client_id, 'buy', 'BAJFINANCE', 'INE296A01024', 40, 7100, 284000, '2024-03-08',
       'Bajaj Finance for high-quality NBFC exposure; AUM growth runway intact.',
       'Priya Sharma' from c5
union all
select client_id, 'buy', 'DRREDDY', 'INE089A01023', 50, 5400, 270000, '2024-05-20',
       'Dr Reddy''s for US generics exposure; complements healthcare allocation.',
       'Priya Sharma' from c5;
