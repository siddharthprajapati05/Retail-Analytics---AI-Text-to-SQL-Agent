-- ============================================================
-- BASELINE SCHEMA — deliberately minimal (PK only, no extra
-- indexes, orders is a plain table, not partitioned).
-- This is the "before" state we benchmark against.
-- ============================================================

DROP TABLE IF EXISTS order_reviews, order_payments, order_items, orders,
    products, product_category_name_translation, sellers, customers CASCADE;

CREATE TABLE customers (
    customer_id             VARCHAR(32) PRIMARY KEY,
    customer_unique_id      VARCHAR(32) NOT NULL,
    customer_zip_code_prefix VARCHAR(10),
    customer_city           VARCHAR(100),
    customer_state          VARCHAR(2)
);

CREATE TABLE sellers (
    seller_id               VARCHAR(32) PRIMARY KEY,
    seller_zip_code_prefix  VARCHAR(10),
    seller_city             VARCHAR(100),
    seller_state             VARCHAR(2)
);

CREATE TABLE product_category_name_translation (
    product_category_name          VARCHAR(100) PRIMARY KEY,
    product_category_name_english  VARCHAR(100)
);

CREATE TABLE products (
    product_id                  VARCHAR(32) PRIMARY KEY,
    product_category_name       VARCHAR(100),
    product_name_length         INT,
    product_description_length  INT,
    product_photos_qty          INT,
    product_weight_g            NUMERIC,
    product_length_cm           NUMERIC,
    product_height_cm           NUMERIC,
    product_width_cm            NUMERIC
);

-- NOTE: no index on order_purchase_timestamp, no partitioning yet.
-- This is the table that will hurt the most at 10M+ rows.
CREATE TABLE orders (
    order_id                        VARCHAR(32) PRIMARY KEY,
    customer_id                     VARCHAR(32) NOT NULL REFERENCES customers(customer_id),
    order_status                    VARCHAR(20),
    order_purchase_timestamp        TIMESTAMP NOT NULL,
    order_approved_at               TIMESTAMP,
    order_delivered_carrier_date    TIMESTAMP,
    order_delivered_customer_date   TIMESTAMP,
    order_estimated_delivery_date   TIMESTAMP
);

CREATE TABLE order_items (
    order_id           VARCHAR(32) NOT NULL REFERENCES orders(order_id),
    order_item_id       INT NOT NULL,
    product_id           VARCHAR(32) NOT NULL REFERENCES products(product_id),
    seller_id             VARCHAR(32) NOT NULL REFERENCES sellers(seller_id),
    shipping_limit_date  TIMESTAMP,
    price                 NUMERIC(10,2) NOT NULL,
    freight_value         NUMERIC(10,2),
    PRIMARY KEY (order_id, order_item_id)
);

CREATE TABLE order_payments (
    order_id               VARCHAR(32) NOT NULL REFERENCES orders(order_id),
    payment_sequential      INT NOT NULL,
    payment_type             VARCHAR(20),
    payment_installments     INT,
    payment_value             NUMERIC(10,2),
    PRIMARY KEY (order_id, payment_sequential)
);

CREATE TABLE order_reviews (
    review_id                VARCHAR(32) PRIMARY KEY,
    order_id                  VARCHAR(32) NOT NULL REFERENCES orders(order_id),
    review_score               INT,
    review_comment_title        VARCHAR(200),
    review_comment_message      TEXT,
    review_creation_date         TIMESTAMP,
    review_answer_timestamp      TIMESTAMP
);
