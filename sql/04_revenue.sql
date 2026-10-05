-- Paid revenue and order-level average check, in KZT. No refunds in this simulation.
SELECT substr(order_time,1,7) AS month, COUNT(*) AS paid_orders,
       COUNT(DISTINCT user_id) AS buyers, SUM(amount_kzt) AS revenue_kzt,
       AVG(amount_kzt) AS average_order_value_kzt
FROM orders WHERE status = 'paid' GROUP BY month ORDER BY month;
