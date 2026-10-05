-- Exact N-Day Retention by signup month. Only users with full observation window.
-- No activity on the exact day => 0. Immature cohorts are excluded from denominator.
WITH horizons AS (SELECT 1 AS n UNION ALL SELECT 7 UNION ALL SELECT 30),
active AS (SELECT DISTINCT user_id, date(event_time) AS day FROM events)
SELECT substr(u.signup_date,1,7) AS cohort, h.n AS day_number,
       COUNT(*) AS eligible_users, COUNT(a.user_id) AS retained_users,
       1.0*COUNT(a.user_id)/NULLIF(COUNT(*),0) AS retention
FROM users u CROSS JOIN horizons h
LEFT JOIN active a ON a.user_id = u.user_id
    AND a.day = date(u.signup_date,'+' || h.n || ' days')
WHERE date(u.signup_date,'+' || h.n || ' days') <= '2026-09-30'
GROUP BY cohort, h.n ORDER BY cohort, h.n;
