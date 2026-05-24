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
-- Diversified across sectors; per-position size ~₹15-45L sized so the
-- total cost basis matches the client's stated aum_cr.
p1 as (
    insert into portfolios (client_id, holdings, benchmark, inception_date)
    select id, '[
        {"ticker":"TCS","company_name":"Tata Consultancy Services","isin":"INE467B01029","qty":650,"buy_price":3200,"sector":"IT","asset_class":"equity","buy_date":"2025-01-15"},
        {"ticker":"INFY","company_name":"Infosys","isin":"INE009A01021","qty":1400,"buy_price":1480,"sector":"IT","asset_class":"equity","buy_date":"2024-11-10"},
        {"ticker":"HDFCBANK","company_name":"HDFC Bank","isin":"INE040A01034","qty":1290,"buy_price":1620,"sector":"BFSI","asset_class":"equity","buy_date":"2024-08-22"},
        {"ticker":"ICICIBANK","company_name":"ICICI Bank","isin":"INE090A01021","qty":1925,"buy_price":1080,"sector":"BFSI","asset_class":"equity","buy_date":"2024-09-05"},
        {"ticker":"RELIANCE","company_name":"Reliance Industries","isin":"INE002A01018","qty":835,"buy_price":2500,"sector":"Energy","asset_class":"equity","buy_date":"2024-02-12"},
        {"ticker":"BHARTIARTL","company_name":"Bharti Airtel","isin":"INE397D01024","qty":2270,"buy_price":920,"sector":"Telecom","asset_class":"equity","buy_date":"2024-04-18"},
        {"ticker":"ITC","company_name":"ITC","isin":"INE154A01025","qty":5100,"buy_price":410,"sector":"FMCG","asset_class":"equity","buy_date":"2024-03-25"},
        {"ticker":"LT","company_name":"Larsen & Toubro","isin":"INE018A01030","qty":595,"buy_price":3500,"sector":"Infrastructure","asset_class":"equity","buy_date":"2024-06-10"},
        {"ticker":"MARUTI","company_name":"Maruti Suzuki India","isin":"INE585B01010","qty":190,"buy_price":11000,"sector":"Auto","asset_class":"equity","buy_date":"2024-07-08"},
        {"ticker":"SUNPHARMA","company_name":"Sun Pharma","isin":"INE044A01036","qty":1780,"buy_price":1170,"sector":"Pharma","asset_class":"equity","buy_date":"2024-09-20"},
        {"ticker":"ASIANPAINT","company_name":"Asian Paints","isin":"INE021A01026","qty":705,"buy_price":2960,"sector":"Materials","asset_class":"equity","buy_date":"2024-10-14"},
        {"ticker":"TITAN","company_name":"Titan Company","isin":"INE280A01028","qty":615,"buy_price":3400,"sector":"Consumer Discretionary","asset_class":"equity","buy_date":"2024-12-02"}
    ]'::jsonb, 'NIFTY50', '2023-04-01'
    from c1
    returning client_id
),
p2 as (
    insert into portfolios (client_id, holdings, benchmark, inception_date)
    select id, '[
        {"ticker":"TCS","company_name":"Tata Consultancy Services","isin":"INE467B01029","qty":350,"buy_price":3400,"sector":"IT","asset_class":"equity","buy_date":"2024-03-12"},
        {"ticker":"INFY","company_name":"Infosys","isin":"INE009A01021","qty":810,"buy_price":1480,"sector":"IT","asset_class":"equity","buy_date":"2024-04-22"},
        {"ticker":"WIPRO","company_name":"Wipro","isin":"INE075A01022","qty":2310,"buy_price":520,"sector":"IT","asset_class":"equity","buy_date":"2024-05-20"},
        {"ticker":"PAYTM","company_name":"One 97 Communications","isin":"INE982J01020","qty":1410,"buy_price":850,"sector":"Fintech","asset_class":"equity","buy_date":"2024-02-08"},
        {"ticker":"BAJFINANCE","company_name":"Bajaj Finance","isin":"INE296A01024","qty":170,"buy_price":7100,"sector":"BFSI","asset_class":"equity","buy_date":"2024-06-14"},
        {"ticker":"HDFCBANK","company_name":"HDFC Bank","isin":"INE040A01034","qty":740,"buy_price":1620,"sector":"BFSI","asset_class":"equity","buy_date":"2024-07-30"},
        {"ticker":"TATAMOTORS","company_name":"Tata Motors","isin":"INE155A01022","qty":1690,"buy_price":710,"sector":"Auto","asset_class":"equity","buy_date":"2024-08-19"},
        {"ticker":"DMART","company_name":"Avenue Supermarts","isin":"INE192R01011","qty":285,"buy_price":4200,"sector":"Retail","asset_class":"equity","buy_date":"2024-09-12"},
        {"ticker":"POLYCAB","company_name":"Polycab India","isin":"INE455K01017","qty":175,"buy_price":6850,"sector":"Capital Goods","asset_class":"equity","buy_date":"2024-10-04"},
        {"ticker":"ADANIENT","company_name":"Adani Enterprises","isin":"INE423A01024","qty":415,"buy_price":2890,"sector":"Conglomerate","asset_class":"equity","buy_date":"2024-11-15"}
    ]'::jsonb, 'NIFTY50', '2024-01-15'
    from c2
    returning client_id
),
p3 as (
    insert into portfolios (client_id, holdings, benchmark, inception_date)
    select id, '[
        {"ticker":"RELIANCE","company_name":"Reliance Industries","isin":"INE002A01018","qty":1330,"buy_price":2500,"sector":"Energy","asset_class":"equity","buy_date":"2022-08-10"},
        {"ticker":"HDFCBANK","company_name":"HDFC Bank","isin":"INE040A01034","qty":2220,"buy_price":1500,"sector":"BFSI","asset_class":"equity","buy_date":"2023-01-15"},
        {"ticker":"ICICIBANK","company_name":"ICICI Bank","isin":"INE090A01021","qty":3085,"buy_price":1080,"sector":"BFSI","asset_class":"equity","buy_date":"2023-03-08"},
        {"ticker":"BHARTIARTL","company_name":"Bharti Airtel","isin":"INE397D01024","qty":3620,"buy_price":920,"sector":"Telecom","asset_class":"equity","buy_date":"2023-06-30"},
        {"ticker":"ITC","company_name":"ITC","isin":"INE154A01025","qty":8120,"buy_price":410,"sector":"FMCG","asset_class":"equity","buy_date":"2023-11-22"},
        {"ticker":"SUNPHARMA","company_name":"Sun Pharma","isin":"INE044A01036","qty":2845,"buy_price":1170,"sector":"Pharma","asset_class":"equity","buy_date":"2024-02-18"},
        {"ticker":"TCS","company_name":"Tata Consultancy Services","isin":"INE467B01029","qty":1040,"buy_price":3200,"sector":"IT","asset_class":"equity","buy_date":"2023-04-05"},
        {"ticker":"INFY","company_name":"Infosys","isin":"INE009A01021","qty":2250,"buy_price":1480,"sector":"IT","asset_class":"equity","buy_date":"2023-08-14"},
        {"ticker":"LT","company_name":"Larsen & Toubro","isin":"INE018A01030","qty":950,"buy_price":3500,"sector":"Infrastructure","asset_class":"equity","buy_date":"2023-09-26"},
        {"ticker":"MARUTI","company_name":"Maruti Suzuki India","isin":"INE585B01010","qty":303,"buy_price":11000,"sector":"Auto","asset_class":"equity","buy_date":"2023-12-11"},
        {"ticker":"ASIANPAINT","company_name":"Asian Paints","isin":"INE021A01026","qty":1125,"buy_price":2960,"sector":"Materials","asset_class":"equity","buy_date":"2024-04-09"},
        {"ticker":"TATASTEEL","company_name":"Tata Steel","isin":"INE081A01020","qty":23800,"buy_price":140,"sector":"Metals","asset_class":"equity","buy_date":"2024-05-22"},
        {"ticker":"TITAN","company_name":"Titan Company","isin":"INE280A01028","qty":980,"buy_price":3400,"sector":"Consumer Discretionary","asset_class":"equity","buy_date":"2024-07-15"},
        {"ticker":"ADANIPORTS","company_name":"Adani Ports & SEZ","isin":"INE742F01042","qty":2565,"buy_price":1300,"sector":"Logistics","asset_class":"equity","buy_date":"2024-08-28"},
        {"ticker":"POWERGRID","company_name":"Power Grid Corporation","isin":"INE752E01010","qty":11100,"buy_price":300,"sector":"Utilities","asset_class":"equity","buy_date":"2024-10-07"}
    ]'::jsonb, 'NIFTY50', '2022-07-01'
    from c3
    returning client_id
),
p4 as (
    insert into portfolios (client_id, holdings, benchmark, inception_date)
    select id, '[
        {"ticker":"HDFCBANK","company_name":"HDFC Bank","isin":"INE040A01034","qty":595,"buy_price":1580,"sector":"BFSI","asset_class":"equity","buy_date":"2024-06-15"},
        {"ticker":"ICICIBANK","company_name":"ICICI Bank","isin":"INE090A01021","qty":870,"buy_price":1080,"sector":"BFSI","asset_class":"equity","buy_date":"2024-07-02"},
        {"ticker":"NESTLEIND","company_name":"Nestle India","isin":"INE239A01016","qty":392,"buy_price":2400,"sector":"FMCG","asset_class":"equity","buy_date":"2024-07-22"},
        {"ticker":"HINDUNILVR","company_name":"Hindustan Unilever","isin":"INE030A01027","qty":412,"buy_price":2280,"sector":"FMCG","asset_class":"equity","buy_date":"2024-08-05"},
        {"ticker":"ITC","company_name":"ITC","isin":"INE154A01025","qty":2295,"buy_price":410,"sector":"FMCG","asset_class":"equity","buy_date":"2024-08-20"},
        {"ticker":"POWERGRID","company_name":"Power Grid Corporation","isin":"INE752E01010","qty":3135,"buy_price":300,"sector":"Utilities","asset_class":"equity","buy_date":"2024-09-09"},
        {"ticker":"COALINDIA","company_name":"Coal India","isin":"INE522F01014","qty":2240,"buy_price":420,"sector":"Mining","asset_class":"equity","buy_date":"2024-10-18"},
        {"ticker":"BAJAJ-AUTO","company_name":"Bajaj Auto","isin":"INE917I01010","qty":105,"buy_price":9000,"sector":"Auto","asset_class":"equity","buy_date":"2024-11-26"}
    ]'::jsonb, 'NIFTY50', '2024-06-01'
    from c4
    returning client_id
),
p5 as (
    insert into portfolios (client_id, holdings, benchmark, inception_date)
    select id, '[
        {"ticker":"TCS","company_name":"Tata Consultancy Services","isin":"INE467B01029","qty":1430,"buy_price":3100,"sector":"IT","asset_class":"equity","buy_date":"2023-09-12"},
        {"ticker":"INFY","company_name":"Infosys","isin":"INE009A01021","qty":3125,"buy_price":1420,"sector":"IT","asset_class":"equity","buy_date":"2023-11-04"},
        {"ticker":"HDFCBANK","company_name":"HDFC Bank","isin":"INE040A01034","qty":2845,"buy_price":1560,"sector":"BFSI","asset_class":"equity","buy_date":"2023-12-18"},
        {"ticker":"ICICIBANK","company_name":"ICICI Bank","isin":"INE090A01021","qty":4110,"buy_price":1080,"sector":"BFSI","asset_class":"equity","buy_date":"2024-01-04"},
        {"ticker":"RELIANCE","company_name":"Reliance Industries","isin":"INE002A01018","qty":1812,"buy_price":2450,"sector":"Energy","asset_class":"equity","buy_date":"2024-01-22"},
        {"ticker":"BAJFINANCE","company_name":"Bajaj Finance","isin":"INE296A01024","qty":625,"buy_price":7100,"sector":"BFSI","asset_class":"equity","buy_date":"2024-03-08"},
        {"ticker":"ASIANPAINT","company_name":"Asian Paints","isin":"INE021A01026","qty":1500,"buy_price":2960,"sector":"Materials","asset_class":"equity","buy_date":"2024-04-15"},
        {"ticker":"DRREDDY","company_name":"Dr Reddy''s Laboratories","isin":"INE089A01023","qty":822,"buy_price":5400,"sector":"Pharma","asset_class":"equity","buy_date":"2024-05-20"},
        {"ticker":"SUNPHARMA","company_name":"Sun Pharma","isin":"INE044A01036","qty":3795,"buy_price":1170,"sector":"Pharma","asset_class":"equity","buy_date":"2024-06-12"},
        {"ticker":"BHARTIARTL","company_name":"Bharti Airtel","isin":"INE397D01024","qty":4825,"buy_price":920,"sector":"Telecom","asset_class":"equity","buy_date":"2024-07-03"},
        {"ticker":"MARUTI","company_name":"Maruti Suzuki India","isin":"INE585B01010","qty":404,"buy_price":11000,"sector":"Auto","asset_class":"equity","buy_date":"2024-07-29"},
        {"ticker":"LT","company_name":"Larsen & Toubro","isin":"INE018A01030","qty":1268,"buy_price":3500,"sector":"Infrastructure","asset_class":"equity","buy_date":"2024-08-21"},
        {"ticker":"ITC","company_name":"ITC","isin":"INE154A01025","qty":10830,"buy_price":410,"sector":"FMCG","asset_class":"equity","buy_date":"2024-09-10"},
        {"ticker":"TITAN","company_name":"Titan Company","isin":"INE280A01028","qty":1305,"buy_price":3400,"sector":"Consumer Discretionary","asset_class":"equity","buy_date":"2024-09-30"},
        {"ticker":"TATASTEEL","company_name":"Tata Steel","isin":"INE081A01020","qty":31700,"buy_price":140,"sector":"Metals","asset_class":"equity","buy_date":"2024-10-22"},
        {"ticker":"DMART","company_name":"Avenue Supermarts","isin":"INE192R01011","qty":1057,"buy_price":4200,"sector":"Retail","asset_class":"equity","buy_date":"2024-11-12"},
        {"ticker":"POLYCAB","company_name":"Polycab India","isin":"INE455K01017","qty":648,"buy_price":6850,"sector":"Capital Goods","asset_class":"equity","buy_date":"2024-12-04"},
        {"ticker":"ADANIENT","company_name":"Adani Enterprises","isin":"INE423A01024","qty":1535,"buy_price":2890,"sector":"Conglomerate","asset_class":"equity","buy_date":"2024-12-26"}
    ]'::jsonb, 'NIFTY50', '2021-01-01'
    from c5
    returning client_id
)

-- ─── A few transactions per client with rationale ─────────────────────
insert into transactions
    (client_id, txn_type, ticker, isin, quantity, price, total_value, txn_date, rationale, executed_by)
select client_id, 'buy', 'TCS', 'INE467B01029', 250, 3200, 800000, '2025-01-15',
       'Added TCS on IT dip — strong deal pipeline visibility from Q3 results.',
       'Priya Sharma' from c1
union all
select client_id, 'buy', 'HDFCBANK', 'INE040A01034', 500, 1620, 810000, '2024-08-22',
       'Initiated BFSI exposure with HDFC Bank post-merger; valuations attractive.',
       'Priya Sharma' from c1
union all
select client_id, 'buy', 'INFY', 'INE009A01021', 550, 1480, 814000, '2024-11-10',
       'Topped up Infosys on margin-guidance dip; remain bullish on US discretionary recovery.',
       'Priya Sharma' from c1
union all
select client_id, 'buy', 'PAYTM', 'INE982J01020', 1410, 850, 1198500, '2024-02-08',
       'Tactical position in Paytm post-RBI overhang; high-risk component of the book.',
       'Priya Sharma' from c2
union all
select client_id, 'buy', 'WIPRO', 'INE075A01022', 2310, 520, 1201200, '2024-05-20',
       'Wipro acquisition to broaden IT mix beyond TCS — diversifies single-name risk.',
       'Priya Sharma' from c2
union all
select client_id, 'buy', 'SUNPHARMA', 'INE044A01036', 2845, 1170, 3328650, '2024-02-18',
       'Added pharma to balance the equity book; specialty US business performing well.',
       'Priya Sharma' from c3
union all
select client_id, 'buy', 'BHARTIARTL', 'INE397D01024', 3620, 920, 3330400, '2023-06-30',
       'Telecom tariff hikes thesis playing out; Airtel positioned well vs peers.',
       'Priya Sharma' from c3
union all
select client_id, 'buy', 'NESTLEIND', 'INE239A01016', 392, 2400, 940800, '2024-07-22',
       'Defensive FMCG addition for income-need profile.',
       'Priya Sharma' from c4
union all
select client_id, 'buy', 'BAJFINANCE', 'INE296A01024', 625, 7100, 4437500, '2024-03-08',
       'Bajaj Finance for high-quality NBFC exposure; AUM growth runway intact.',
       'Priya Sharma' from c5
union all
select client_id, 'buy', 'DRREDDY', 'INE089A01023', 822, 5400, 4438800, '2024-05-20',
       'Dr Reddy''s for US generics exposure; complements healthcare allocation.',
       'Priya Sharma' from c5;
