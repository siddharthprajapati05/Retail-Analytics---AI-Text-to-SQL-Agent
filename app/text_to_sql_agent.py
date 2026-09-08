"""
Schema-grounded Text-to-SQL agent.

Flow: natural-language question -> Gemini generates SQL (schema in the
prompt) -> SQL is validated as read-only SELECT -> executed against
Postgres -> Gemini turns the result rows into a plain-English answer +
one-line business recommendation.

Run standalone for a quick sanity check:
    python text_to_sql_agent.py "What were our top 5 selling categories last month?"
"""
import json
import os
import re
import sys

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
_client = None  # lazy-initialised on first call


def _get_client():
    """Return a Gemini client, initialising it on first use."""
    global _client
    if _client is None:
        from google import genai
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. "
                "Add it to your .env file (get a free key at https://aistudio.google.com/app/apikey)."
            )
        _client = genai.Client(api_key=api_key)
    return _client

SCHEMA_CONTEXT = """
Tables (Postgres):

customers(customer_id PK, customer_unique_id, customer_zip_code_prefix, customer_city, customer_state)
sellers(seller_id PK, seller_zip_code_prefix, seller_city, seller_state)
products(product_id PK, product_category_name, product_name_length, product_description_length,
         product_photos_qty, product_weight_g, product_length_cm, product_height_cm, product_width_cm)
product_category_name_translation(product_category_name PK, product_category_name_english)
orders(order_id, customer_id FK->customers, order_status, order_purchase_timestamp,
       order_approved_at, order_delivered_carrier_date, order_delivered_customer_date,
       order_estimated_delivery_date)   -- PARTITIONED by month on order_purchase_timestamp,
                                          -- PK is (order_id, order_purchase_timestamp)
order_items(order_id, order_item_id, product_id FK->products, seller_id FK->sellers,
            shipping_limit_date, price, freight_value)   -- PK (order_id, order_item_id)
order_payments(order_id, payment_sequential, payment_type, payment_installments, payment_value)
order_reviews(review_id PK, order_id, review_score, review_comment_title,
              review_comment_message, review_creation_date, review_answer_timestamp)

Notes:
- order_status values include: delivered, shipped, canceled, unavailable, processing, invoiced
- revenue = SUM(order_items.price + order_items.freight_value) unless the question implies otherwise
- always filter order_status = 'delivered' for revenue/LTV questions unless the user asks about all orders
"""

FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|alter|truncate|grant|revoke|create)\b", re.I)


def generate_sql(question: str) -> str:
    prompt = (
        "You are a senior data analyst. Given a Postgres schema and a business "
        "question, write ONE read-only SELECT query that answers it. "
        "Return ONLY the SQL, no markdown fences, no commentary.\n\n"
        f"Schema:\n{SCHEMA_CONTEXT}\n\nQuestion: {question}"
    )
    resp = _get_client().models.generate_content(model=MODEL, contents=prompt)
    sql = resp.text.strip()
    sql = re.sub(r"^```sql\s*|```$", "", sql, flags=re.M).strip()
    return sql


def validate_sql(sql: str) -> None:
    if not sql.lower().lstrip().startswith("select") and not sql.lower().lstrip().startswith("with"):
        raise ValueError("Generated query is not a SELECT/CTE — refusing to run it.")
    if FORBIDDEN.search(sql):
        raise ValueError(f"Generated query contains a forbidden keyword — refusing to run it.\nSQL: {sql}")
    if ";" in sql.rstrip(";"):
        raise ValueError("Generated query contains multiple statements — refusing to run it.")


def run_sql(sql: str, limit: int = 200):
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    # Read-only, bounded-time safety net at the session level
    with conn.cursor() as cur:
        cur.execute("SET default_transaction_read_only = on;")
        cur.execute("SET statement_timeout = '10s';")
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql)
            rows = cur.fetchmany(limit)
    finally:
        conn.close()
    return rows


def summarize(question: str, sql: str, rows: list) -> str:
    prompt = (
        "You are a data analyst reporting to a business stakeholder. Given a "
        "question, the SQL used, and the result rows, write a short plain-English "
        "answer (2-4 sentences) followed by one concrete recommendation. No jargon.\n\n"
        f"Question: {question}\n\nSQL: {sql}\n\nResults (JSON): {json.dumps(rows, default=str)[:4000]}"
    )
    resp = _get_client().models.generate_content(model=MODEL, contents=prompt)
    return resp.text.strip()


def ask(question: str) -> dict:
    sql = generate_sql(question)
    validate_sql(sql)
    rows = run_sql(sql)
    answer = summarize(question, sql, rows)
    return {"question": question, "sql": sql, "rows": rows, "answer": answer}


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "What is our total revenue by month?"
    result = ask(q)
    print("\nSQL:\n", result["sql"])
    print(f"\n{len(result['rows'])} rows returned")
    print("\nAnswer:\n", result["answer"])
