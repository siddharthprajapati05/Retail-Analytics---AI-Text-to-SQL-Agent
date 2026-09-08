"""
Run with: venv/bin/python -m streamlit run app/streamlit_app.py
"""
import json
import os
import time

import pandas as pd
import plotly.express as px
import psycopg2
from psycopg2.extras import RealDictCursor
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from text_to_sql_agent import ask

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Retail Analytics & AI Text-to-SQL Agent",
    page_icon="🛒",
    layout="wide",
)

# ── Global CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Dark header bar */
.main-header {
    background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
    border-radius: 16px;
    padding: 28px 36px;
    margin-bottom: 28px;
    border: 1px solid rgba(99,179,237,0.15);
    box-shadow: 0 4px 32px rgba(0,0,0,0.4);
}
.main-header h1 {
    color: #e2e8f0;
    font-size: 2rem;
    font-weight: 700;
    margin: 0 0 4px 0;
    letter-spacing: -0.5px;
}
.main-header p {
    color: #718096;
    font-size: 0.95rem;
    margin: 0;
}

/* Terminal editor wrapper */
.terminal-wrapper {
    background: #0d1117;
    border-radius: 12px;
    border: 1px solid #30363d;
    overflow: hidden;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5);
}
.terminal-titlebar {
    background: #161b22;
    padding: 10px 16px;
    display: flex;
    align-items: center;
    gap: 8px;
    border-bottom: 1px solid #30363d;
}
.dot { width:12px; height:12px; border-radius:50%; display:inline-block; }
.dot-red   { background:#ff5f56; }
.dot-yellow{ background:#ffbd2e; }
.dot-green { background:#27c93f; }
.terminal-label {
    color: #8b949e;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    margin-left: 8px;
}

/* Metric cards */
.metric-row { display:flex; gap:16px; margin-bottom:20px; flex-wrap:wrap; }
.metric-card {
    flex:1; min-width:140px;
    background: linear-gradient(135deg, #1a1a2e, #16213e);
    border: 1px solid rgba(99,179,237,0.2);
    border-radius: 12px;
    padding: 16px 20px;
    text-align:center;
}
.metric-card .val {
    font-size:1.6rem; font-weight:700; color:#63b3ed; line-height:1;
}
.metric-card .lbl {
    font-size:0.75rem; color:#718096; margin-top:4px; text-transform:uppercase; letter-spacing:0.5px;
}

/* History pills */
.hist-pill {
    display:inline-block;
    background:#1a1a2e;
    border:1px solid #30363d;
    border-radius:20px;
    padding:4px 14px;
    font-family:'JetBrains Mono', monospace;
    font-size:0.72rem;
    color:#8b949e;
    margin:3px;
    cursor:pointer;
    transition:all .2s;
}
.hist-pill:hover { border-color:#63b3ed; color:#63b3ed; }

/* Status badges */
.badge-ok  { background:#1a4731; color:#68d391; border:1px solid #276749; border-radius:6px; padding:3px 10px; font-size:0.78rem; font-weight:600; }
.badge-err { background:#4a1a1a; color:#fc8181; border:1px solid #742a2a; border-radius:6px; padding:3px 10px; font-size:0.78rem; font-weight:600; }

/* Dataframe tweaks */
[data-testid="stDataFrame"] { border-radius:10px; overflow:hidden; }

/* Tab styling */
[data-testid="stTab"] button { font-weight:500; }

/* Schema explorer */
.schema-table-card {
    background: linear-gradient(135deg, #0d1117, #161b22);
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 18px 20px;
    margin-bottom: 12px;
    transition: border-color .2s;
}
.schema-table-card:hover { border-color: #63b3ed; }
.schema-table-name {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1rem;
    font-weight: 600;
    color: #63b3ed;
    margin: 0 0 4px 0;
}
.schema-row-count {
    font-size: 0.78rem;
    color: #68d391;
    background: #1a4731;
    border: 1px solid #276749;
    border-radius: 20px;
    padding: 2px 10px;
    display: inline-block;
    margin-left: 8px;
    font-weight: 600;
}
.col-chip {
    display: inline-block;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    background: #1a1a2e;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 3px 8px;
    margin: 2px;
    color: #c9d1d9;
}
.col-chip .col-type { color: #b794f4; margin-left: 4px; }
.col-chip .col-pk   { color: #f6ad55; margin-left: 3px; font-size:0.65rem; }
.col-chip .col-fk   { color: #68d391; margin-left: 3px; font-size:0.65rem; }
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
  <h1>🛒 Retail Analytics & AI Text-to-SQL Agent</h1>
  <p>SQL terminal &nbsp;·&nbsp; AI text-to-SQL agent &nbsp;·&nbsp; Query performance lab</p>
</div>
""", unsafe_allow_html=True)

# ── Session state init ─────────────────────────────────────────────────────────
if "sql_history" not in st.session_state:
    st.session_state.sql_history = []
if "last_result_df" not in st.session_state:
    st.session_state.last_result_df = None
if "last_exec_ms" not in st.session_state:
    st.session_state.last_exec_ms = None
if "last_status" not in st.session_state:
    st.session_state.last_status = None
if "last_error" not in st.session_state:
    st.session_state.last_error = None


# ── Helpers ───────────────────────────────────────────────────────────────────
FORBIDDEN_SQL = {"insert", "update", "delete", "drop", "alter", "truncate", "grant", "revoke", "create"}

def run_raw_sql(sql: str, limit: int = 500):
    """Execute a read-only SELECT and return (DataFrame, elapsed_ms)."""
    first_word = sql.strip().split()[0].lower() if sql.strip() else ""
    if first_word not in ("select", "with", "explain"):
        raise ValueError("Only SELECT / WITH / EXPLAIN queries are allowed.")
    for kw in FORBIDDEN_SQL:
        import re
        if re.search(rf"\b{kw}\b", sql, re.I):
            raise ValueError(f"Forbidden keyword detected: {kw.upper()}")

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            cur.execute("SET default_transaction_read_only = on;")
            cur.execute("SET statement_timeout = '15s';")
        t0 = time.perf_counter()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql)
            rows = cur.fetchmany(limit)
        elapsed_ms = (time.perf_counter() - t0) * 1000
    finally:
        conn.close()

    df = pd.DataFrame([dict(r) for r in rows])
    return df, elapsed_ms


@st.cache_data(ttl=60)
def get_schema():
    """Fetch all user tables with columns, types, pk/fk flags, and row counts."""
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Columns + PK info
            cur.execute("""
                SELECT
                    c.table_name,
                    c.column_name,
                    c.data_type,
                    c.character_maximum_length,
                    c.is_nullable,
                    CASE WHEN pk.column_name IS NOT NULL THEN TRUE ELSE FALSE END AS is_pk
                FROM information_schema.columns c
                LEFT JOIN (
                    SELECT ku.table_name, ku.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage ku
                      ON tc.constraint_name = ku.constraint_name
                     AND tc.table_schema = ku.table_schema
                    WHERE tc.constraint_type = 'PRIMARY KEY'
                      AND tc.table_schema = 'public'
                ) pk ON pk.table_name = c.table_name AND pk.column_name = c.column_name
                WHERE c.table_schema = 'public'
                ORDER BY c.table_name, c.ordinal_position;
            """)
            cols_rows = [dict(r) for r in cur.fetchall()]

            # FK info
            cur.execute("""
                SELECT
                    kcu.table_name,
                    kcu.column_name,
                    ccu.table_name AS foreign_table
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage ccu
                  ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public';
            """)
            fk_rows = {(r["table_name"], r["column_name"]): r["foreign_table"] for r in cur.fetchall()}

            # Row counts from stats (fast estimate)
            cur.execute("""
                SELECT relname AS table_name, n_live_tup AS row_count
                FROM pg_stat_user_tables
                ORDER BY relname;
            """)
            row_counts = {r["table_name"]: r["row_count"] for r in cur.fetchall()}
    finally:
        conn.close()

    # Group by table
    tables = {}
    for row in cols_rows:
        tname = row["table_name"]
        if tname not in tables:
            tables[tname] = {"columns": [], "row_count": row_counts.get(tname, 0)}
        dtype = row["data_type"]
        if row["character_maximum_length"]:
            dtype = f"varchar({row['character_maximum_length']})"
        tables[tname]["columns"].append({
            "name": row["column_name"],
            "type": dtype,
            "nullable": row["is_nullable"] == "YES",
            "is_pk": row["is_pk"],
            "fk_to": fk_rows.get((tname, row["column_name"])),
        })
    return tables


def get_table_preview(table_name: str, limit: int = 5):
    """Fetch the first N rows of a table as a DataFrame."""
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"SELECT * FROM {table_name} LIMIT %s", (limit,))
            rows = cur.fetchall()
    finally:
        conn.close()
    return pd.DataFrame([dict(r) for r in rows])


SAMPLE_QUERIES = [
    ("Monthly revenue", "SELECT\n  DATE_TRUNC('month', o.order_purchase_timestamp) AS month,\n  ROUND(SUM(oi.price + oi.freight_value)::numeric, 2) AS revenue\nFROM orders o\nJOIN order_items oi ON oi.order_id = o.order_id\nWHERE o.order_status = 'delivered'\nGROUP BY 1\nORDER BY 1;"),
    ("Top 10 sellers", "SELECT\n  s.seller_id,\n  s.seller_city,\n  s.seller_state,\n  ROUND(SUM(oi.price)::numeric, 2) AS total_revenue,\n  COUNT(DISTINCT oi.order_id) AS orders\nFROM order_items oi\nJOIN sellers s ON s.seller_id = oi.seller_id\nGROUP BY 1,2,3\nORDER BY total_revenue DESC\nLIMIT 10;"),
    ("Avg review score by category", "SELECT\n  COALESCE(t.product_category_name_english, p.product_category_name) AS category,\n  ROUND(AVG(r.review_score)::numeric, 2) AS avg_score,\n  COUNT(*) AS reviews\nFROM order_reviews r\nJOIN order_items oi ON oi.order_id = r.order_id\nJOIN products p ON p.product_id = oi.product_id\nLEFT JOIN product_category_name_translation t ON t.product_category_name = p.product_category_name\nGROUP BY 1\nHAVING COUNT(*) > 50\nORDER BY avg_score DESC\nLIMIT 15;"),
    ("Orders by status", "SELECT order_status, COUNT(*) AS cnt\nFROM orders\nGROUP BY order_status\nORDER BY cnt DESC;"),
    ("Top 5 states by customers", "SELECT customer_state, COUNT(*) AS customers\nFROM customers\nGROUP BY customer_state\nORDER BY customers DESC\nLIMIT 5;"),
]

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_sql, tab_schema, tab_ai, tab_perf = st.tabs([
    "🖥️  SQL Terminal",
    "🗂️  Schema Explorer",
    "🤖  AI Assistant",
    "📊  Performance Lab",
])

# ════════════════════════════════════════════════════════════════════════════════
# TAB 1 — SQL Terminal
# ════════════════════════════════════════════════════════════════════════════════
with tab_sql:
    col_editor, col_sidebar = st.columns([3, 1], gap="large")

    with col_sidebar:
        st.markdown("#### 📋 Sample Queries")
        st.caption("Click to load into editor")
        for label, q in SAMPLE_QUERIES:
            if st.button(label, key=f"sample_{label}", use_container_width=True):
                st.session_state["_sql_prefill"] = q
                st.rerun()

        if st.session_state.sql_history:
            st.markdown("---")
            st.markdown("#### 🕘 Recent")
            for i, h in enumerate(reversed(st.session_state.sql_history[-8:])):
                preview = h[:50].replace("\n", " ") + ("…" if len(h) > 50 else "")
                if st.button(preview, key=f"hist_{i}", use_container_width=True):
                    st.session_state["_sql_prefill"] = h
                    st.rerun()

    with col_editor:
        # Terminal chrome
        st.markdown("""
        <div class="terminal-wrapper">
          <div class="terminal-titlebar">
            <span class="dot dot-red"></span>
            <span class="dot dot-yellow"></span>
            <span class="dot dot-green"></span>
            <span class="terminal-label">retail_db — postgres@localhost:5432</span>
          </div>
        </div>
        """, unsafe_allow_html=True)

        default_sql = st.session_state.pop("_sql_prefill", "SELECT * FROM orders LIMIT 20;")

        sql_query = st.text_area(
            label="SQL Query",
            value=default_sql,
            height=220,
            placeholder="SELECT * FROM orders LIMIT 10;",
            label_visibility="collapsed",
            key="sql_input",
        )

        c1, c2, c3 = st.columns([1, 1, 4])
        run_clicked = c1.button("▶  Run", type="primary", use_container_width=True)
        clear_clicked = c2.button("✕  Clear", use_container_width=True)

        if clear_clicked:
            st.session_state.last_result_df = None
            st.session_state.last_exec_ms = None
            st.session_state.last_status = None
            st.session_state.last_error = None
            st.rerun()

        if run_clicked and sql_query.strip():
            with st.spinner("Executing…"):
                try:
                    df, elapsed_ms = run_raw_sql(sql_query)
                    st.session_state.last_result_df = df
                    st.session_state.last_exec_ms = elapsed_ms
                    st.session_state.last_status = "ok"
                    st.session_state.last_error = None
                    if sql_query not in st.session_state.sql_history:
                        st.session_state.sql_history.append(sql_query)
                except Exception as e:
                    st.session_state.last_result_df = None
                    st.session_state.last_exec_ms = None
                    st.session_state.last_status = "error"
                    st.session_state.last_error = str(e)

        # ── Results ────────────────────────────────────────────────────────────
        if st.session_state.last_status == "error":
            st.markdown(f'<span class="badge-err">✗ ERROR</span>', unsafe_allow_html=True)
            st.error(st.session_state.last_error)

        elif st.session_state.last_status == "ok":
            df = st.session_state.last_result_df
            ms = st.session_state.last_exec_ms

            # Status + metrics row
            badge = '<span class="badge-ok">✓ OK</span>'
            rows_lbl = f"{len(df):,} row{'s' if len(df) != 1 else ''}"
            cols_lbl = f"{len(df.columns)} col{'s' if len(df.columns) != 1 else ''}"
            st.markdown(
                f'{badge} &nbsp; <span style="color:#718096;font-size:.85rem">'
                f'{rows_lbl} &nbsp;·&nbsp; {cols_lbl} &nbsp;·&nbsp; {ms:.1f} ms</span>',
                unsafe_allow_html=True,
            )

            if df.empty:
                st.info("Query returned 0 rows.")
            else:
                st.dataframe(df, use_container_width=True, height=380)

                # Auto-chart: if there's a numeric col + a label col, plot a bar
                num_cols = df.select_dtypes("number").columns.tolist()
                str_cols = df.select_dtypes("object").columns.tolist()
                if num_cols and str_cols and len(df) <= 200:
                    with st.expander("📈 Auto-visualise"):
                        x_col = st.selectbox("X axis (label)", str_cols, key="x_sel")
                        y_col = st.selectbox("Y axis (value)", num_cols, key="y_sel")
                        chart_type = st.radio("Chart", ["Bar", "Line", "Scatter"], horizontal=True, key="chart_type")
                        if chart_type == "Bar":
                            fig = px.bar(df, x=x_col, y=y_col, color_discrete_sequence=["#63b3ed"])
                        elif chart_type == "Line":
                            fig = px.line(df, x=x_col, y=y_col, color_discrete_sequence=["#63b3ed"])
                        else:
                            fig = px.scatter(df, x=x_col, y=y_col, color_discrete_sequence=["#63b3ed"])
                        fig.update_layout(
                            paper_bgcolor="#0d1117",
                            plot_bgcolor="#0d1117",
                            font_color="#c9d1d9",
                            xaxis=dict(gridcolor="#30363d"),
                            yaxis=dict(gridcolor="#30363d"),
                        )
                        st.plotly_chart(fig, width="stretch")

                # Download
                st.download_button(
                    "⬇ Download CSV",
                    df.to_csv(index=False).encode(),
                    file_name="query_result.csv",
                    mime="text/csv",
                )


# ════════════════════════════════════════════════════════════════════════════════
# TAB 2 — Schema Explorer
# ════════════════════════════════════════════════════════════════════════════════
with tab_schema:
    st.markdown("""
    <div style="background:linear-gradient(135deg,#0f0f1a,#1a1a2e);border-radius:12px;
                padding:20px 24px;margin-bottom:20px;border:1px solid rgba(99,179,237,0.15)">
      <h4 style="color:#e2e8f0;margin:0 0 6px 0">🗂️ Live Database Schema</h4>
      <p style="color:#718096;margin:0;font-size:.9rem">
        All tables, columns, data types, primary keys, foreign keys, and row counts — live from Postgres.
      </p>
    </div>
    """, unsafe_allow_html=True)

    try:
        schema = get_schema()
    except Exception as e:
        st.error(f"Could not connect to database: {e}")
        schema = {}

    if schema:
        # Top-level DB stats
        total_rows = sum(t["row_count"] for t in schema.values())
        total_cols = sum(len(t["columns"]) for t in schema.values())
        s1, s2, s3 = st.columns(3)
        s1.metric("Tables", len(schema))
        s2.metric("Total columns", total_cols)
        s3.metric("Total rows (estimate)", f"{total_rows:,}")

        st.markdown("---")

        # Select a table to preview
        table_names = sorted(schema.keys())
        selected_table = st.selectbox(
            "👆 Select a table to preview its data",
            options=[""] + table_names,
            format_func=lambda x: "— choose a table —" if x == "" else x,
        )

        st.markdown("### Tables")

        # Render each table card
        for tname in table_names:
            info = schema[tname]
            row_count = info["row_count"]
            cols = info["columns"]

            # Build column chips HTML
            chips = ""
            for col in cols:
                badges = ""
                if col["is_pk"]:
                    badges += '<span class="col-pk">PK</span>'
                if col["fk_to"]:
                    badges += f'<span class="col-fk">→{col["fk_to"]}</span>'
                chips += (
                    f'<span class="col-chip">'
                    f'{col["name"]}'
                    f'<span class="col-type">{col["type"]}</span>'
                    f'{badges}</span>'
                )

            st.markdown(
                f'<div class="schema-table-card">'
                f'<p class="schema-table-name">'
                f'📋 {tname}'
                f'<span class="schema-row-count">{row_count:,} rows</span>'
                f'</p>'
                f'<div style="margin-top:8px;line-height:2">{chips}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Live data preview
        if selected_table:
            st.markdown(f"### 🔍 Preview: `{selected_table}`")
            try:
                preview_df = get_table_preview(selected_table, limit=10)
                st.dataframe(preview_df, use_container_width=True)

                # Quick-fill SQL terminal button
                quick_sql = f"SELECT *\nFROM {selected_table}\nLIMIT 50;"
                if st.button(f"▶ Open in SQL Terminal", key="open_in_terminal"):
                    st.session_state["_sql_prefill"] = quick_sql
                    st.rerun()
            except Exception as e:
                st.error(f"Could not preview {selected_table}: {e}")


# ════════════════════════════════════════════════════════════════════════════════
# TAB 3 — AI Assistant
# ════════════════════════════════════════════════════════════════════════════════
with tab_ai:
    st.markdown("""
    <div style="background:linear-gradient(135deg,#0f0f1a,#1a1a2e);border-radius:12px;
                padding:20px 24px;margin-bottom:20px;border:1px solid rgba(99,179,237,0.15)">
      <h4 style="color:#e2e8f0;margin:0 0 6px 0">🤖 Ask in plain English</h4>
      <p style="color:#718096;margin:0;font-size:.9rem">
        The AI generates a validated read-only SQL query, runs it, and gives you a plain-English answer + recommendation.
      </p>
    </div>
    """, unsafe_allow_html=True)

    example_questions = [
        "What are our top 5 product categories by revenue?",
        "Which state has the most customers?",
        "What is the average review score per product category?",
        "How many orders were delivered vs cancelled?",
        "Who are our top 10 sellers by total sales?",
    ]
    st.markdown("**Try one of these:**")
    eq_cols = st.columns(3)
    for i, eq in enumerate(example_questions):
        if eq_cols[i % 3].button(eq, key=f"eq_{i}"):
            st.session_state["_ai_prefill"] = eq
            st.rerun()

    st.markdown("---")
    ai_question = st.text_input(
        "Your question",
        value=st.session_state.pop("_ai_prefill", ""),
        placeholder="e.g. What is our total revenue by month?",
    )

    if st.button("🔍 Ask Gemini", type="primary") and ai_question:
        with st.spinner("Gemini is thinking…"):
            try:
                result = ask(ai_question)
                st.success("Done!")

                st.markdown("#### 💬 Answer")
                st.markdown(
                    f'<div style="background:#1a1a2e;border-left:3px solid #63b3ed;'
                    f'padding:16px 20px;border-radius:0 8px 8px 0;color:#e2e8f0;line-height:1.7">'
                    f'{result["answer"]}</div>',
                    unsafe_allow_html=True,
                )

                with st.expander("🔎 Generated SQL"):
                    st.code(result["sql"], language="sql")

                with st.expander(f"📋 Raw results ({len(result['rows'])} rows)"):
                    if result["rows"]:
                        rdf = pd.DataFrame(result["rows"])
                        st.dataframe(rdf, use_container_width=True)
                        st.download_button(
                            "⬇ Download CSV",
                            rdf.to_csv(index=False).encode(),
                            file_name="ai_result.csv",
                            mime="text/csv",
                        )
                    else:
                        st.write("No rows returned.")

            except Exception as e:
                st.error(f"Error: {e}")


# ════════════════════════════════════════════════════════════════════════════════
# TAB 3 — Performance Lab
# ════════════════════════════════════════════════════════════════════════════════
with tab_perf:
    st.caption("Query latency before vs. after indexing + monthly partitioning — from scripts/benchmark.py")

    before_path = os.path.join(RESULTS_DIR, "before.json")
    after_path  = os.path.join(RESULTS_DIR, "after.json")

    if not (os.path.exists(before_path) and os.path.exists(after_path)):
        st.info(
            "Run `venv/bin/python scripts/benchmark.py --label before`, "
            "apply `sql/02_indexes_and_partitioning.sql`, "
            "then `--label after` to populate this tab."
        )
    else:
        with open(before_path) as f:
            before = {r["query"]: r.get("execution_time_ms") for r in json.load(f)}
        with open(after_path) as f:
            after = {r["query"]: r.get("execution_time_ms") for r in json.load(f)}

        df_perf = pd.DataFrame(
            [{"query": n, "stage": "before", "ms": before.get(n)} for n in before]
            + [{"query": n, "stage": "after",  "ms": after.get(n)}  for n in after]
        ).dropna()

        # Summary metrics
        avg_before = df_perf[df_perf.stage == "before"]["ms"].mean()
        avg_after  = df_perf[df_perf.stage == "after"]["ms"].mean()
        speedup    = avg_before / avg_after if avg_after else 0

        m1, m2, m3 = st.columns(3)
        m1.metric("Avg latency before", f"{avg_before:.0f} ms")
        m2.metric("Avg latency after",  f"{avg_after:.0f} ms",  delta=f"{avg_after-avg_before:.0f} ms")
        m3.metric("Average speedup",    f"{speedup:.1f}×")

        fig = px.bar(
            df_perf, x="query", y="ms", color="stage", barmode="group",
            title="Query execution time — before vs. after optimization",
            labels={"ms": "Execution time (ms)", "query": ""},
            color_discrete_map={"before": "#fc8181", "after": "#68d391"},
        )
        fig.update_layout(
            paper_bgcolor="#0d1117",
            plot_bgcolor="#0d1117",
            font_color="#c9d1d9",
            xaxis=dict(gridcolor="#30363d", tickangle=-20),
            yaxis=dict(gridcolor="#30363d"),
            legend=dict(bgcolor="rgba(0,0,0,0)"),
        )
        st.plotly_chart(fig, width="stretch")

        summary = (
            df_perf.pivot(index="query", columns="stage", values="ms")
            .assign(speedup=lambda d: (d["before"] / d["after"]).round(1))
        )
        st.dataframe(summary, use_container_width=True)
