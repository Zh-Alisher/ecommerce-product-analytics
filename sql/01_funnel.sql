-- Session-level funnel; rates are fractions (0..1), not percentages.
WITH counts AS (
    SELECT COUNT(*) AS views, COUNT(cart_time) AS carts,
           COUNT(checkout_time) AS checkouts, COUNT(purchase_time) AS purchases
    FROM session_funnel
)
SELECT 1 AS step, 'view' AS event_name, views AS sessions,
       1.0 AS conversion_from_previous, 1.0 AS conversion_from_view FROM counts
UNION ALL
SELECT 2, 'add_to_cart', carts, 1.0*carts/NULLIF(views,0), 1.0*carts/NULLIF(views,0) FROM counts
UNION ALL
SELECT 3, 'checkout', checkouts, 1.0*checkouts/NULLIF(carts,0), 1.0*checkouts/NULLIF(views,0) FROM counts
UNION ALL
SELECT 4, 'purchase', purchases, 1.0*purchases/NULLIF(checkouts,0), 1.0*purchases/NULLIF(views,0) FROM counts
ORDER BY step;
