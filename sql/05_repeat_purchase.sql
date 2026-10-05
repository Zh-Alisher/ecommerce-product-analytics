-- Second purchase within 30 days of first. Include only fully observed first buyers.
WITH ranked AS (
    SELECT user_id, order_time,
           ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY order_time,order_id) AS rn
    FROM orders WHERE status = 'paid'
), buyer_dates AS (
    SELECT user_id,
           MIN(CASE WHEN rn=1 THEN date(order_time) END) AS first_day,
           MIN(CASE WHEN rn=2 THEN date(order_time) END) AS second_day
    FROM ranked GROUP BY user_id
)
SELECT COUNT(*) AS eligible_buyers,
       SUM(CASE WHEN second_day <= date(first_day,'+30 days') THEN 1 ELSE 0 END) AS repeat_buyers_30d,
       1.0*SUM(CASE WHEN second_day <= date(first_day,'+30 days') THEN 1 ELSE 0 END)
           /NULLIF(COUNT(*),0) AS repeat_purchase_rate_30d
FROM buyer_dates WHERE date(first_day,'+30 days') <= '2026-09-30';
