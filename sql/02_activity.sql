-- Active = at least one event. Zero-activity calendar days are included.
-- WAU and MAU are trailing 7/30-day active users, including the current day.
WITH RECURSIVE calendar(day) AS (
    SELECT '2026-06-01' UNION ALL
    SELECT date(day, '+1 day') FROM calendar WHERE day < '2026-09-30'
), active AS (
    SELECT DISTINCT user_id, date(event_time) AS day FROM events
)
SELECT c.day,
       COUNT(DISTINCT CASE WHEN a.day = c.day THEN a.user_id END) AS dau,
       COUNT(DISTINCT CASE WHEN a.day >= date(c.day,'-6 days') THEN a.user_id END) AS wau,
       COUNT(DISTINCT a.user_id) AS mau
FROM calendar c LEFT JOIN active a
    ON a.day BETWEEN date(c.day,'-29 days') AND c.day
GROUP BY c.day ORDER BY c.day;
