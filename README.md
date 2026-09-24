# 🛒 Retail Analytics & AI Text-to-SQL Agent

A full-stack data analytics project built on a real Brazilian e-commerce dataset (Olist, ~100K orders scaled to 10M+ rows). It combines **SQL performance engineering** (indexing, partitioning, query benchmarking) with an **AI-powered Text-to-SQL agent** that lets anyone ask business questions in plain English and get instant answers.

---

## 📖 What This Project Does

### Part 1 — SQL Performance Lab
The database starts with **no indexes** (only primary keys) — simulating a freshly migrated production database. Six real business queries (revenue trends, top sellers, customer lifetime value, repeat purchase rate, delivery times, category trends) are benchmarked using `EXPLAIN ANALYZE`. Then composite indexes and monthly range partitioning are applied, and the same queries are benchmarked again. The Streamlit dashboard shows a side-by-side before/after comparison chart proving the performance improvement.

### Part 2 — AI Text-to-SQL Agent
A non-technical user types a business question in English like *"What are our top 5 product categories by revenue?"*. The AI agent (powered by Google Gemini) generates a validated read-only SQL query, executes it safely against Postgres (with a 10-second timeout and write-blocking), and returns a plain-English answer along with a business recommendation.

---

## 🔧 Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Database** | PostgreSQL 15 (Docker) | EXPLAIN ANALYZE, range partitioning, real query plans |
| **Dataset** | Olist Kaggle e-commerce + synthetic scale-up | Real data distributions, scaled to 10M+ rows |
| **AI Agent** | Google Gemini (`gemini-2.0-flash`) | Schema-grounded natural language → SQL generation |
| **Dashboard** | Streamlit + Plotly | Interactive SQL terminal, AI assistant, performance charts |
| **Language** | Python 3.10+ | pandas, psycopg2, google-genai, Faker |
| **Container** | Docker | Isolated, reproducible Postgres instance with persistent volume |

---

## 🏗️ Architecture

```
Olist CSV files (data/raw/)
        │
        ▼  scripts/load_data.py
PostgreSQL — baseline schema (8 tables, PK only, no indexes)
        │
        ▼  scripts/generate_synthetic_scale.py
PostgreSQL — scaled to 10M+ rows (2016–2026)
        │
        ├──► scripts/benchmark.py --label before   → results/before.json
        │
        ▼  sql/02_indexes_and_partitioning.sql
PostgreSQL — optimized (composite indexes + monthly partitions)
        │
        └──► scripts/benchmark.py --label after    → results/after.json
                                │
                                ▼
              app/streamlit_app.py
              ├── Tab 1: SQL Terminal (run any SELECT query)
              ├── Tab 2: Schema Explorer (live table/column info)
              ├── Tab 3: AI Assistant (Gemini → SQL → answer)
              └── Tab 4: Performance Lab (before/after chart)
```

---

## 🗂️ Folder Structure

```
data-analyst-project/
├── .env                         ← secrets (DATABASE_URL + GEMINI_API_KEY)
├── .env.example                 ← template
├── requirements.txt             ← all Python dependencies
├── README.md
│
├── data/raw/                    ← 8 Olist CSV files (~60 MB)
│
├── sql/
│   ├── 01_schema_baseline.sql           ← creates 8 tables (PK only)
│   ├── 02_indexes_and_partitioning.sql  ← adds indexes + monthly partitions
│   └── 03_business_queries.sql          ← 6 benchmark queries
│
├── scripts/
│   ├── load_data.py                 ← loads CSVs into Postgres
│   ├── generate_synthetic_scale.py  ← scales to 10M+ rows using Faker
│   └── benchmark.py                 ← runs EXPLAIN ANALYZE, saves JSON
│
├── app/
│   ├── text_to_sql_agent.py     ← Gemini-powered NL → SQL agent
│   └── streamlit_app.py         ← 4-tab Streamlit dashboard
│
└── results/
    ├── before.json              ← benchmark timings before optimization
    └── after.json               ← benchmark timings after optimization
```

---

## 📊 How Indexing & Partitioning Work in This Project

### The Problem (Before Optimization)

The baseline schema (`01_schema_baseline.sql`) creates 8 tables with **only primary keys** — no secondary indexes at all. When the database has 10M+ rows, every business query forces PostgreSQL to do a **sequential scan** (reading every single row in the table). This is extremely slow.

For example, a query like *"What is our monthly revenue?"* requires joining `orders` with `order_items`, filtering by `order_status = 'delivered'`, and grouping by month. Without indexes, Postgres scans all 10M+ order rows and all order_items rows end to end.

### The Solution — Composite Indexes

The optimization script (`02_indexes_and_partitioning.sql`) adds **targeted indexes** on the exact columns that the business queries filter and join on:

| Index | Table | Column(s) | Why |
|---|---|---|---|
| `idx_order_items_order_id` | order_items | order_id | Speeds up JOIN between orders ↔ order_items |
| `idx_order_items_product_id` | order_items | product_id | Speeds up JOIN with products table |
| `idx_order_items_seller_id` | order_items | seller_id | Speeds up seller revenue queries |
| `idx_order_payments_order_id` | order_payments | order_id | Speeds up payment lookups by order |
| `idx_order_reviews_order_id` | order_reviews | order_id | Speeds up review lookups by order |
| `idx_products_category` | products | product_category_name | Speeds up category-based aggregations |
| `idx_customers_state` | customers | customer_state | Speeds up state-based delivery time queries |
| `idx_orders_customer_id` | orders | customer_id | Speeds up customer lifetime value queries |

**How indexes help:** Instead of scanning millions of rows, Postgres uses a **B-tree index** to jump directly to the matching rows — like using a book's index instead of reading every page.

### The Solution — Monthly Range Partitioning

The `orders` table is the largest and most frequently filtered by date. The optimization script converts it into a **range-partitioned table** split by `order_purchase_timestamp`, creating one partition per month (e.g., `orders_2024_01`, `orders_2024_02`, …).

**How partitioning helps:** When a query filters by date range (e.g., *"last 6 months"*), Postgres uses **partition pruning** — it only reads the relevant monthly partitions and completely skips all other months. On 10M+ rows spread across 120+ monthly partitions, this can eliminate 95%+ of the data from being scanned.

Each monthly partition also gets its own index on `(order_status, order_purchase_timestamp)`, so within a partition, filtered lookups are fast too.

### The Trade-off

Partitioning requires the partition key (`order_purchase_timestamp`) to be part of the primary key. So the PK changes from `(order_id)` to `(order_id, order_purchase_timestamp)`. This means foreign keys from `order_items`, `order_payments`, and `order_reviews` pointing to `orders(order_id)` must be dropped — Postgres cannot enforce a FK unless it matches the full PK of a partitioned table. Data integrity is handled at the application level instead. This is a real-world trade-off that production systems commonly make.

### The 6 Benchmark Queries

| Query | Business Question | What It Tests |
|---|---|---|
| `monthly_revenue` | What's our monthly revenue trend? | Full table scan + JOIN + GROUP BY on dates |
| `top_sellers_last_6_months` | Top 10 sellers by revenue (last 6 months)? | Date range filter + partition pruning |
| `top_100_customers_ltv` | Top 100 customers by lifetime value? | Large JOIN + aggregation + sort |
| `repeat_purchase_rate` | What % of customers have 2+ orders? | CTE + GROUP BY + filter |
| `avg_delivery_time_by_state` | Slowest states by avg delivery time? | JOIN customers + date math |
| `category_revenue_trend` | Revenue trend per product category? | 3-table JOIN + GROUP BY month + category |

---

## How to Run This Project

### Prerequisites
- Docker Desktop installed and running
- Python 3.10+
- Free Google Gemini API key → https://aistudio.google.com/app/apikey

---

## 🔧 First-Time Setup (run once)

### Step 1 — Clone the repo

```bash
git clone https://github.com/siddharthprajapati05/Retail-Analytics---AI-Text-to-SQL-Agent.git
cd Retail-Analytics---AI-Text-to-SQL-Agent
```

---

### Step 2 — Create and activate virtual environment

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
```

---

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

---

### Step 4 — Start PostgreSQL in Docker

```bash
docker run -d \
  --name retail-postgres \
  -v retail-pgdata:/var/lib/postgresql/data \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=retail_db \
  -p 5432:5432 \
  postgres:15
```

> **Port conflict?** If port 5432 is already in use:
> ```bash
> docker ps                          # find the container using port 5432
> docker stop <container_name>       # stop it
> ```
> Then run the command above again.

---

### Step 5 — Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and set your values:
```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/retail_db
GEMINI_API_KEY=your_gemini_api_key_here
```

---

### Step 6 — Create the database schema

```bash
docker exec -i retail-postgres psql -U postgres -d retail_db < sql/01_schema_baseline.sql
```

---

### Step 7 — Load the Olist dataset

```bash
venv/bin/python scripts/load_data.py --data-dir data/raw
```

---

### Step 8 — Scale up to 10M+ rows (optional)

```bash
venv/bin/python scripts/generate_synthetic_scale.py --target-rows 10000000
```

> Takes ~5–10 minutes. Skip this step if you just want to test quickly.

---

### Step 9 — Benchmark BEFORE optimization

```bash
venv/bin/python scripts/benchmark.py --label before
```

---

### Step 10 — Apply indexes and partitioning

```bash
docker exec -i retail-postgres psql -U postgres -d retail_db < sql/02_indexes_and_partitioning.sql
```

---

### Step 11 — Benchmark AFTER optimization

```bash
venv/bin/python scripts/benchmark.py --label after
```

---

## 🚀 Every Time You Start (after first-time setup)

### Step 1 — Start the containers and activate venv

```bash
docker start retail-postgres
source venv/bin/activate
```

### Step 2 — Launch the Streamlit app

```bash
venv/bin/python -m streamlit run app/streamlit_app.py
```

Open → **http://localhost:8501**
