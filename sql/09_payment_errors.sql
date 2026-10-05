-- Explicit failure telemetry among sessions that reached checkout.
WITH errors AS (
    SELECT DISTINCT session_id FROM events WHERE event_name='payment_error'
)
SELECT substr(f.view_time,1,7) AS month,f.platform,f.app_version,
       COUNT(*) AS checkout_sessions, COUNT(e.session_id) AS error_sessions,
       1.0*COUNT(e.session_id)/COUNT(*) AS payment_error_rate
FROM session_funnel f LEFT JOIN errors e ON e.session_id=f.session_id
WHERE f.checkout_time IS NOT NULL
GROUP BY month,f.platform,f.app_version ORDER BY month,f.platform,f.app_version;
