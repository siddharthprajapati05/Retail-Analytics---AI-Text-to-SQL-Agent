-- ============================================================
-- OPTIMIZATION MIGRATION — run this AFTER benchmark.py --label before
-- Two changes:
--   1) Targeted indexes on the join/filter columns the business
--      queries actually use.
--   2) Convert `orders` (the biggest, most time-filtered table)
--      into a monthly RANGE-partitioned table.
--
-- TRADE-OFF CALLED OUT ON PURPOSE: Postgres requires any unique/PK
-- constraint on a partitioned table to include the partition key.
-- So the new `orders` PK becomes (order_id, order_purchase_timestamp)
-- instead of just (order_id), which means we can no longer enforce
-- FKs from order_items/order_payments/order_reviews -> orders at the
-- database level (those tables only store order_id, not the
-- timestamp). We drop those FKs and rely on application-level
-- integrity instead. This is a real, common partitioning trade-off —
-- be ready to explain it, it's a good interview talking point.
-- ============================================================

-- ---------- 1. Indexes on the non-partitioned tables ----------

CREATE INDEX IF NOT EXISTS idx_order_items_order_id   ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product_id ON order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_order_items_seller_id  ON order_items(seller_id);

CREATE INDEX IF NOT EXISTS idx_order_payments_order_id ON order_payments(order_id);

CREATE INDEX IF NOT EXISTS idx_order_reviews_order_id  ON order_reviews(order_id);

CREATE INDEX IF NOT EXISTS idx_products_category ON products(product_category_name);

CREATE INDEX IF NOT EXISTS idx_customers_state ON customers(customer_state);
CREATE INDEX IF NOT EXISTS idx_sellers_state   ON sellers(seller_state);

-- ---------- 2. Drop FKs that reference orders(order_id) alone ----------

ALTER TABLE order_items   DROP CONSTRAINT IF EXISTS order_items_order_id_fkey;
ALTER TABLE order_payments DROP CONSTRAINT IF EXISTS order_payments_order_id_fkey;
ALTER TABLE order_reviews  DROP CONSTRAINT IF EXISTS order_reviews_order_id_fkey;

-- ---------- 3. Rebuild `orders` as a partitioned table ----------

ALTER TABLE orders RENAME TO orders_old;

CREATE TABLE orders (
    order_id                        VARCHAR(32) NOT NULL,
    customer_id                     VARCHAR(32) NOT NULL REFERENCES customers(customer_id),
    order_status                    VARCHAR(20),
    order_purchase_timestamp        TIMESTAMP NOT NULL,
    order_approved_at               TIMESTAMP,
    order_delivered_carrier_date    TIMESTAMP,
    order_delivered_customer_date   TIMESTAMP,
    order_estimated_delivery_date   TIMESTAMP,
    PRIMARY KEY (order_id, order_purchase_timestamp)
) PARTITION BY RANGE (order_purchase_timestamp);

-- Composite index used heavily by the status + date-range business queries
CREATE INDEX idx_orders_customer_id ON orders(customer_id);

-- ---------- 4. Auto-create one partition per month covering the data ----------

DO $$
DECLARE
    min_ts     TIMESTAMP;
    max_ts     TIMESTAMP;
    part_start DATE;
    part_end   DATE;
    part_name  TEXT;
BEGIN
    SELECT date_trunc('month', MIN(order_purchase_timestamp)),
           date_trunc('month', MAX(order_purchase_timestamp)) + INTERVAL '1 month'
      INTO min_ts, max_ts
      FROM orders_old;

    part_start := min_ts::DATE;
    WHILE part_start < max_ts::DATE LOOP
        part_end  := (part_start + INTERVAL '1 month')::DATE;
        part_name := 'orders_' || to_char(part_start, 'YYYY_MM');

        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF orders
             FOR VALUES FROM (%L) TO (%L);',
            part_name, part_start, part_end
        );

        -- index each partition on status+timestamp for the filtered range scans
        EXECUTE format(
            'CREATE INDEX IF NOT EXISTS %I ON %I (order_status, order_purchase_timestamp);',
            part_name || '_status_ts_idx', part_name
        );

        part_start := part_end;
    END LOOP;

    -- catch-all partition for anything outside the generated range
    EXECUTE 'CREATE TABLE IF NOT EXISTS orders_default PARTITION OF orders DEFAULT;';
END $$;

-- ---------- 5. Copy data across, then drop the old table ----------

INSERT INTO orders
SELECT * FROM orders_old;

DROP TABLE orders_old;

-- ---------- 6. Sanity checks ----------

-- Should show one row per monthly partition + orders_default
SELECT inhrelid::regclass AS partition_name
FROM pg_inherits
WHERE inhparent = 'orders'::regclass
ORDER BY 1;

ANALYZE orders;
ANALYZE order_items;
ANALYZE order_payments;
