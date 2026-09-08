"""
Scales the real Olist data up to production-like volume.

Strategy: reuse real customer_id / product_id / seller_id pools (so
referential integrity holds with zero extra work), and real price /
freight distributions sampled with jitter, but generate many more
`orders` + `order_items` rows spread across an extended date range
(so the monthly-partitioning story has years of data to show off,
not just Olist's real 2016-2018 window).

Usage:
    python generate_synthetic_scale.py --target-rows 10000000
    python generate_synthetic_scale.py --target-rows 2000000   # quick local test
"""
import argparse
import os
import random
import uuid
from datetime import timedelta

import numpy as np
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

STATUS_WEIGHTS = {
    "delivered": 0.92, "shipped": 0.03, "canceled": 0.02,
    "unavailable": 0.01, "processing": 0.01, "invoiced": 0.01,
}

BATCH_SIZE = 20_000


def fetch_pools(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT customer_id FROM customers")
        customer_ids = [r[0] for r in cur.fetchall()]

        cur.execute("SELECT product_id FROM products")
        product_ids = [r[0] for r in cur.fetchall()]

        cur.execute("SELECT seller_id FROM sellers")
        seller_ids = [r[0] for r in cur.fetchall()]

        cur.execute("SELECT price, freight_value FROM order_items LIMIT 50000")
        price_rows = cur.fetchall()

        cur.execute("SELECT MIN(order_purchase_timestamp), MAX(order_purchase_timestamp) FROM orders")
        min_ts, max_ts = cur.fetchone()

    prices = np.array([float(p) for p, _ in price_rows if p is not None])
    freights = np.array([float(f) for _, f in price_rows if f is not None])
    return customer_ids, product_ids, seller_ids, prices, freights, min_ts, max_ts


def weighted_status():
    return random.choices(list(STATUS_WEIGHTS.keys()), weights=list(STATUS_WEIGHTS.values()))[0]


def gen_batch(n_orders, customer_ids, product_ids, seller_ids, prices, freights, min_ts, max_ts):
    """Returns (orders_rows, order_items_rows) for n_orders synthetic orders."""
    span_days = (max_ts - min_ts).days + 365 * 8  # extend 8 years past the real data
    orders_rows = []
    items_rows = []

    for _ in range(n_orders):
        order_id = uuid.uuid4().hex
        customer_id = random.choice(customer_ids)
        status = weighted_status()

        purchase_ts = min_ts + timedelta(
            days=random.uniform(0, span_days),
            seconds=random.randint(0, 86399),
        )
        approved_ts = purchase_ts + timedelta(hours=random.uniform(1, 48))
        carrier_ts = approved_ts + timedelta(days=random.uniform(0.5, 3))
        delivered_ts = carrier_ts + timedelta(days=random.uniform(1, 15)) if status == "delivered" else None
        estimated_ts = purchase_ts + timedelta(days=random.uniform(7, 30))

        orders_rows.append((
            order_id, customer_id, status, purchase_ts, approved_ts,
            carrier_ts, delivered_ts, estimated_ts,
        ))

        n_items = random.choices([1, 2, 3, 4], weights=[0.7, 0.18, 0.08, 0.04])[0]
        for item_idx in range(1, n_items + 1):
            price = float(np.random.choice(prices)) * random.uniform(0.85, 1.15)
            freight = float(np.random.choice(freights)) * random.uniform(0.85, 1.15)
            items_rows.append((
                order_id, item_idx, random.choice(product_ids), random.choice(seller_ids),
                purchase_ts, round(price, 2), round(freight, 2),
            ))

    return orders_rows, items_rows


def insert_batch(conn, orders_rows, items_rows):
    with conn.cursor() as cur:
        execute_values(
            cur,
            """INSERT INTO orders (order_id, customer_id, order_status,
               order_purchase_timestamp, order_approved_at,
               order_delivered_carrier_date, order_delivered_customer_date,
               order_estimated_delivery_date) VALUES %s""",
            orders_rows,
        )
        execute_values(
            cur,
            """INSERT INTO order_items (order_id, order_item_id, product_id,
               seller_id, shipping_limit_date, price, freight_value) VALUES %s""",
            items_rows,
        )
    conn.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-rows", type=int, default=5_000_000,
                         help="target row count for order_items (orders will be ~40%% of this)")
    args = parser.parse_args()

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    customer_ids, product_ids, seller_ids, prices, freights, min_ts, max_ts = fetch_pools(conn)

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM order_items")
        current_items = cur.fetchone()[0]

    remaining_items = max(args.target_rows - current_items, 0)
    # ~2.3 items per order on average given the weights above
    orders_needed = int(remaining_items / 2.3)
    print(f"Currently {current_items:,} order_items. Generating ~{orders_needed:,} more orders "
          f"to reach ~{args.target_rows:,} order_items.")

    n_batches = max(orders_needed // BATCH_SIZE, 1)
    for _ in tqdm(range(n_batches), desc="Generating synthetic orders"):
        orders_rows, items_rows = gen_batch(
            BATCH_SIZE, customer_ids, product_ids, seller_ids, prices, freights, min_ts, max_ts
        )
        insert_batch(conn, orders_rows, items_rows)

    conn.close()
    print("Done. Re-run scripts/benchmark.py to measure the impact.")


if __name__ == "__main__":
    main()
