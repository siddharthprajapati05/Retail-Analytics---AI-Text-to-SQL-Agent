# 🛒 Retail Analytics & AI Text-to-SQL Agent — SQL Performance Lab + AI Text-to-SQL Agent

A portfolio project for data-analyst roles that combines **real SQL engineering** (indexing, partitioning, query diagnosis) with an **AI agent** that lets non-technical users ask business questions in plain English.

---

## 📖 What is this project?

You are working with a real Brazilian e-commerce dataset (Olist, ~100k orders) loaded into PostgreSQL.

The project has **two main parts**:

### Part 1 — SQL Performance Lab
- The database starts with **no indexes** (just primary keys) — just like a freshly migrated production DB.
- Six real business queries are benchmarked (revenue trends, top sellers, customer LTV, etc.).
- Then **composite indexes** and **monthly range partitioning** on the orders table are applied.
- The same queries are benchmarked again to measure the speedup.
- Both runs are plotted side-by-side in the Streamlit dashboard.

### Part 2 — AI Text-to-SQL Agent
- Powered by **Google Gemini** (`gemini-2.0-flash` by default).
- A non-technical user types a business question in English, e.g. *"What are our top 5 product categories by revenue this year?"*
- The agent generates a **read-only SELECT query**, runs it safely against Postgres, and returns a plain-English answer + a business recommendation.
- The query is validated (no INSERT/UPDATE/DROP allowed) and has a 10-second timeout.

---

## 🏗️ Architecture

```
Olist CSV files (data/raw/)
        │
        ▼  scripts/load_data.py
PostgreSQL — baseline schema (no indexes)
        │
        ▼  scripts/generate_synthetic_scale.py
PostgreSQL — scaled to 10M+ rows (2016–2026)
        │
        ├──► scripts/benchmark.py --label before   → results/before.json
        │
        ▼  sql/02_indexes_and_partitioning.sql
PostgreSQL — optimized (indexes + monthly partitions)
        │
        └──► scripts/benchmark.py --label after    → results/after.json
                                │
                                ▼
              app/streamlit_app.py
              ├── Tab 1: Ask a question (Gemini → SQL → DB → answer)
              └── Tab 2: Before/after performance chart
```

---

## 🗂️ Folder Structure

```
retail-data-analyst-project/
├── .env                         ← your secrets (DATABASE_URL + GEMINI_API_KEY)
├── .env.example                 ← template
├── README.md
│
├── data/
│   └── raw/                     ← 8 Olist CSV files (~60MB, pre-included)
│
├── sql/
│   ├── 01_schema_baseline.sql           ← creates all 8 tables (PK only)
│   ├── 02_indexes_and_partitioning.sql  ← optimization migration
│   └── 03_business_queries.sql          ← the 6 benchmark queries
│
├── scripts/
│   ├── load_data.py                 ← loads CSVs into Postgres
│   ├── generate_synthetic_scale.py  ← scales to 10M+ rows
│   ├── benchmark.py                 ← runs EXPLAIN ANALYZE, saves JSON
│   └── requirements.txt
│
├── app/
│   ├── text_to_sql_agent.py     ← Gemini-powered NL→SQL agent
│   └── streamlit_app.py         ← the web dashboard
│
└── results/
    ├── before.json              ← benchmark timings before optimization
    └── after.json               ← benchmark timings after optimization
```

---

## ⚡ Quick Start — Every Command in Sequence

### Prerequisites
- Docker Desktop running
- Python 3.10+
- A free Google Gemini API key → https://aistudio.google.com/app/apikey

---

### Step 0 — Set up the Python virtual environment

```bash
cd retail-data-analyst-project

python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r scripts/requirements.txt
pip install google-genai streamlit plotly python-dotenv psycopg2-binary
```

---

### Step 1 — Start PostgreSQL in Docker

```bash
docker run -d \
  --name retail-postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=retail_db \
  -p 5432:5432 \
  postgres:15
```

> If the container already exists: `docker start retail-postgres`

Verify it is running:
```bash
docker ps | grep retail-postgres
```

---

### Step 2 — Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your key:
```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/retail_db
GEMINI_API_KEY=your_key_here
```

---

### Step 3 — Create the database schema

```bash
docker exec -i retail-postgres psql -U postgres -d retail_db < sql/01_schema_baseline.sql
```

Expected output: `CREATE TABLE` x8

---

### Step 4 — Load the real Olist data

```bash
venv/bin/python scripts/load_data.py --data-dir data/raw
```

Expected output:
```
Connected. Loading from data/raw ...
  loaded  99,441 rows -> customers
  loaded   3,095 rows -> sellers
  loaded      71 rows -> product_category_name_translation
  loaded  32,951 rows -> products
  loaded  99,441 rows -> orders
  loaded 112,650 rows -> order_items
  loaded 103,886 rows -> order_payments
  loaded 100,000 rows -> order_reviews
Done.
```

---

### Step 5 — Scale up to 10M+ rows (optional but recommended)

Generates synthetic orders to simulate production-scale data:

```bash
venv/bin/python scripts/generate_synthetic_scale.py --target-rows 10000000
```

> Takes ~5-10 minutes. Skip if you just want to test the app quickly.

---

### Step 6 — Benchmark BEFORE optimization

```bash
venv/bin/python scripts/benchmark.py --label before
```

Saves timings to `results/before.json`.

---

### Step 7 — Apply indexes and partitioning

```bash
docker exec -i retail-postgres psql -U postgres -d retail_db < sql/02_indexes_and_partitioning.sql
```

This adds composite indexes on join/filter columns and converts `orders` into
monthly RANGE partitions (one partition per month, 2016-2026).

---

### Step 8 — Benchmark AFTER optimization

```bash
venv/bin/python scripts/benchmark.py --label after
```

Compare both runs in the terminal:
```bash
venv/bin/python scripts/benchmark.py --compare
```

---

### Step 9 — Launch the Streamlit dashboard

```bash
venv/bin/python -m streamlit run app/streamlit_app.py
```

Open → **http://localhost:8501**

- **Tab "Ask a business question"**: Type any question in English, get SQL + answer.
- **Tab "Query performance"**: Before/after bar chart of all 6 benchmark queries.

---

## 🔧 Tech Stack

| Layer | Tool | Why |
|---|---|---|
| Database | PostgreSQL 15 (Docker) | Real EXPLAIN ANALYZE, range partitioning |
| Data | Olist Kaggle dataset + synthetic scale-up | Real distributions, production-scale volume |
| AI Agent | Google Gemini (gemini-2.0-flash) | Fast, free-tier, schema-grounded prompts |
| Dashboard | Streamlit + Plotly | Live demo in minutes |
| Language | Python 3.12 | pandas, psycopg2, google-genai |

---

## 💡 Useful psql Commands

```bash
# Open an interactive SQL shell
docker exec -it retail-postgres psql -U postgres -d retail_db

# Check row counts in all tables
docker exec -i retail-postgres psql -U postgres -d retail_db \
  -c "SELECT schemaname, tablename, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC;"

# List all monthly partitions of the orders table
docker exec -i retail-postgres psql -U postgres -d retail_db \
  -c "SELECT inhrelid::regclass FROM pg_inherits WHERE inhparent='orders'::regclass ORDER BY 1;"

# Reset everything (drops and recreates all tables)
docker exec -i retail-postgres psql -U postgres -d retail_db < sql/01_schema_baseline.sql
```

---

## 🤔 Common Issues

| Problem | Fix |
|---|---|
| `KeyError: 'DATABASE_URL'` | Add `DATABASE_URL=...` to `.env`, or export it in your shell |
| `NumericValueOutOfRange` on load | Use `venv/bin/python` — already fixed in load_data.py |
| `ModuleNotFoundError: psycopg2` | Run `venv/bin/pip install psycopg2-binary` |
| Streamlit uses wrong Python | Always launch as `venv/bin/python -m streamlit run app/streamlit_app.py` |
| `GEMINI_API_KEY` missing | Add key to `.env`; get one free at https://aistudio.google.com/app/apikey |

---

## 📄 Resume Bullets (fill in your real numbers)

- Built a retail analytics pipeline on a **10M+ row PostgreSQL** dataset (Olist e-commerce schema); diagnosed slow business queries via `EXPLAIN ANALYZE` and reduced p95 latency by **X%** through composite indexing and monthly range partitioning.
- Benchmarked 6 production-style business queries (revenue trends, cohort retention, top-seller LTV); documented before/after query plans showing sequential-scan to index-scan and partition-pruning improvements.
- Built a schema-grounded **Text-to-SQL agent** (Google Gemini API) that translates natural-language business questions into validated, read-only SQL with a plain-English recommendation; deployed as a live Streamlit app.
