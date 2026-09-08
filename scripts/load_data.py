"""
Loads the real Olist Kaggle CSVs (data/raw/*.csv) into the baseline
Postgres schema (sql/01_schema_baseline.sql must already be applied).

Usage:
    python load_data.py --data-dir data/raw
"""
import argparse
import os

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

# (csv filename, table name, {csv_col: db_col} rename map, ordered db columns)
# NOTE: the real Olist CSVs misspell "length" as "lenght" — renamed here.
TABLES = [
    (
        "olist_customers_dataset.csv", "customers",
        {}, ["customer_id", "customer_unique_id", "customer_zip_code_prefix",
             "customer_city", "customer_state"],
    ),
    (
        "olist_sellers_dataset.csv", "sellers",
        {}, ["seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"],
    ),
    (
        "product_category_name_translation.csv", "product_category_name_translation",
        {}, ["product_category_name", "product_category_name_english"],
    ),
    (
        "olist_products_dataset.csv", "products",
        {"product_name_lenght": "product_name_length",
         "product_description_lenght": "product_description_length"},
        ["product_id", "product_category_name", "product_name_length",
         "product_description_length", "product_photos_qty", "product_weight_g",
         "product_length_cm", "product_height_cm", "product_width_cm"],
    ),
    (
        "olist_orders_dataset.csv", "orders",
        {}, ["order_id", "customer_id", "order_status", "order_purchase_timestamp",
             "order_approved_at", "order_delivered_carrier_date",
             "order_delivered_customer_date", "order_estimated_delivery_date"],
    ),
    (
        "olist_order_items_dataset.csv", "order_items",
        {}, ["order_id", "order_item_id", "product_id", "seller_id",
             "shipping_limit_date", "price", "freight_value"],
    ),
    (
        "olist_order_payments_dataset.csv", "order_payments",
        {}, ["order_id", "payment_sequential", "payment_type",
             "payment_installments", "payment_value"],
    ),
    (
        "olist_order_reviews_dataset.csv", "order_reviews",
        {}, ["review_id", "order_id", "review_score", "review_comment_title",
             "review_comment_message", "review_creation_date",
             "review_answer_timestamp"],
    ),
]


def load_table(conn, data_dir, filename, table, rename_map, columns):
    path = os.path.join(data_dir, filename)
    if not os.path.exists(path):
        print(f"  ! skipping {table}: {path} not found")
        return

    df = pd.read_csv(path)
    df = df.rename(columns=rename_map)

    # Only keep columns that actually exist in this CSV — some open mirrors
    # of the dataset drop a column or two (e.g. order_items without
    # shipping_limit_date). Any DB column we don't have data for is left
    # out of the INSERT entirely and gets its table default (NULL).
    present_cols = [c for c in columns if c in df.columns]
    missing_cols = [c for c in columns if c not in df.columns]
    if missing_cols:
        print(f"  ! {table}: source CSV is missing {missing_cols}, inserting NULL for them")
    df = df[present_cols]

    # Postgres INTEGER columns reject Python floats (e.g. 40.0 → error).
    # Coerce float columns whose values are all whole numbers to pandas nullable
    # Int64 *before* calling .where(), which would convert float64 → object and
    # hide the columns from select_dtypes(include="float").
    for col in df.select_dtypes(include="float").columns:
        non_null = df[col].dropna()
        if non_null.empty or (non_null == non_null.astype("int64")).all():
            df[col] = df[col].astype(pd.Int64Dtype())

    # Replace remaining NaN / NaT with None so psycopg2 sends SQL NULL.
    df = df.where(pd.notnull(df), None)

    # de-dupe on primary-key-ish leading columns to avoid load failures
    # (Olist's real CSVs are already clean, this is just a safety net
    # for whatever you feed the pipeline later)
    df = df.drop_duplicates()

    def _to_python(v):
        """Convert numpy scalars / pandas NA to Python-native types for psycopg2."""
        if v is None:
            return None
        try:
            import numpy as np
            if isinstance(v, (np.integer,)):
                return int(v)
            if isinstance(v, (np.floating,)):
                return None if np.isnan(v) else float(v)
        except ImportError:
            pass
        # pandas NA / NAType
        try:
            import pandas as pd
            if pd.isna(v):
                return None
        except (TypeError, ValueError):
            pass
        return v

    rows = [tuple(_to_python(v) for v in r)
            for r in df.itertuples(index=False, name=None)]
    cols_sql = ", ".join(present_cols)
    query = f"INSERT INTO {table} ({cols_sql}) VALUES %s ON CONFLICT DO NOTHING"

    with conn.cursor() as cur:
        execute_values(cur, query, rows, page_size=5000)
    conn.commit()
    print(f"  loaded {len(rows):>7,} rows -> {table}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data/raw")
    args = parser.parse_args()

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    print(f"Connected. Loading from {args.data_dir} ...")
    for filename, table, rename_map, columns in TABLES:
        load_table(conn, args.data_dir, filename, table, rename_map, columns)
    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
