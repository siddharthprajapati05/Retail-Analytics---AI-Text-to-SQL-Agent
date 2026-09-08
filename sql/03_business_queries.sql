-- ============================================================
-- Six business questions, used as the benchmark suite by
-- scripts/benchmark.py. Each is tagged with `-- @query: <name>`
-- so the harness can split this file and run + EXPLAIN ANALYZE
-- each one individually, before and after the migration.
-- Keep the tags and the blank line after each query intact.
-- ============================================================

-- @query: monthly_revenue
-- "What's our monthly revenue trend?"
SELECT date_trunc('month', o.order_purchase_timestamp) AS month,
       SUM(oi.price + oi.freight_value)                AS revenue,
       COUNT(DISTINCT o.order_id)                       AS orders
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.order_status = 'delivered'
GROUP BY 1
ORDER BY 1;

-- @query: top_sellers_last_6_months
-- "Who are our top 10 sellers by revenue in the last 6 months of data?"
SELECT oi.seller_id,
       SUM(oi.price)         AS revenue,
       COUNT(*)              AS items_sold
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
WHERE o.order_purchase_timestamp >= (SELECT MAX(order_purchase_timestamp) FROM orders) - INTERVAL '6 months'
  AND o.order_status = 'delivered'
GROUP BY oi.seller_id
ORDER BY revenue DESC
LIMIT 10;

-- @query: top_100_customers_ltv
-- "Who are our top 100 customers by lifetime value?"
SELECT o.customer_id,
       SUM(oi.price + oi.freight_value) AS lifetime_value,
       COUNT(DISTINCT o.order_id)        AS num_orders
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.order_status = 'delivered'
GROUP BY o.customer_id
ORDER BY lifetime_value DESC
LIMIT 100;

-- @query: repeat_purchase_rate
-- "What share of customers have placed more than one order?"
WITH order_counts AS (
    SELECT customer_id, COUNT(*) AS n_orders
    FROM orders
    WHERE order_status = 'delivered'
    GROUP BY customer_id
)
SELECT
    COUNT(*) FILTER (WHERE n_orders > 1)::NUMERIC / NULLIF(COUNT(*), 0) AS repeat_rate,
    COUNT(*) AS total_customers
FROM order_counts;

-- @query: avg_delivery_time_by_state
-- "Which states have the slowest average delivery time?"
SELECT c.customer_state,
       AVG(EXTRACT(EPOCH FROM (o.order_delivered_customer_date - o.order_purchase_timestamp)) / 86400.0) AS avg_delivery_days,
       COUNT(*) AS num_orders
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
WHERE o.order_status = 'delivered'
  AND o.order_delivered_customer_date IS NOT NULL
GROUP BY c.customer_state
ORDER BY avg_delivery_days DESC;

-- @query: category_revenue_trend
-- "How is revenue trending month over month for each product category?"
SELECT date_trunc('month', o.order_purchase_timestamp) AS month,
       COALESCE(t.product_category_name_english, p.product_category_name) AS category,
       SUM(oi.price) AS revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN products p ON p.product_id = oi.product_id
LEFT JOIN product_category_name_translation t ON t.product_category_name = p.product_category_name
WHERE o.order_status = 'delivered'
GROUP BY 1, 2
ORDER BY 1, revenue DESC;
