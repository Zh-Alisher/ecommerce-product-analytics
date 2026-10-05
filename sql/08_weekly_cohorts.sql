-- Weekly signup cohorts; exact return at D0/D7/D14/D21/D28.
WITH horizons AS (SELECT 0 AS n UNION ALL SELECT 7 UNION ALL SELECT 14 UNION ALL SELECT 21 UNION ALL SELECT 28),
cohorts AS (
    SELECT user_id, signup_date,
           date(signup_date, '-' || ((CAST(strftime('%w',signup_date) AS INTEGER)+6)%7) || ' days') AS cohort_week
    FROM users
), active AS (SELECT DISTINCT user_id,date(event_time) AS day FROM events)
SELECT u.cohort_week, h.n AS day_number, COUNT(*) AS eligible_users,
       COUNT(a.user_id) AS retained_users, 1.0*COUNT(a.user_id)/COUNT(*) AS retention
FROM cohorts u CROSS JOIN horizons h LEFT JOIN active a
    ON a.user_id=u.user_id AND a.day=date(u.signup_date,'+' || h.n || ' days')
WHERE date(u.signup_date,'+' || h.n || ' days') <= '2026-09-30'
GROUP BY u.cohort_week,h.n ORDER BY u.cohort_week,h.n;
