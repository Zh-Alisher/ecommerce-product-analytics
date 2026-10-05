-- Segment by platform x version x month; event properties belong to each session.
SELECT substr(view_time,1,7) AS month, platform, app_version,
       COUNT(*) AS sessions, COUNT(cart_time) AS carts,
       COUNT(checkout_time) AS checkouts, COUNT(purchase_time) AS purchases,
       1.0*COUNT(purchase_time)/NULLIF(COUNT(checkout_time),0) AS checkout_conversion,
       1.0*COUNT(purchase_time)/NULLIF(COUNT(*),0) AS session_conversion
FROM session_funnel GROUP BY month, platform, app_version
ORDER BY month, platform, app_version;
