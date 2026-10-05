-- Acquisition channel is fixed at signup. Comparisons are descriptive, not causal.
WITH orders_per_user AS (
    SELECT user_id, COUNT(*) AS paid_orders, SUM(amount_kzt) AS revenue_kzt
    FROM orders WHERE status='paid' GROUP BY user_id
)
SELECT u.acquisition_channel, COUNT(*) AS users,
       COUNT(o.user_id) AS buyers,
       1.0*COUNT(o.user_id)/NULLIF(COUNT(*),0) AS user_purchase_conversion,
       SUM(COALESCE(o.paid_orders,0)) AS paid_orders,
       SUM(COALESCE(o.revenue_kzt,0)) AS revenue_kzt,
       1.0*SUM(COALESCE(o.revenue_kzt,0))/NULLIF(COUNT(*),0) AS revenue_per_registered_user_kzt
FROM users u LEFT JOIN orders_per_user o ON o.user_id=u.user_id
GROUP BY u.acquisition_channel ORDER BY revenue_per_registered_user_kzt DESC;
