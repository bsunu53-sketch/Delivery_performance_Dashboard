"""
Delivery Performance & Logistics Analytics Dashboard
=====================================================
A Streamlit dashboard for delivery/shipping performance analysis, built
around a DataCo-style supply-chain schema (order date, shipping mode,
late_delivery_risk, scheduled vs. actual shipping days, region, market,
customer segment).

Run with:
    streamlit run dashboard.py

Data sources supported (pick in the sidebar):
    1. Live database (any SQLAlchemy-compatible URI: Postgres, MySQL, SQLite, etc.)
    2. Upload a CSV/Excel file
    3. Built-in sample data (for demoing / testing the dashboard layout)
"""

import io
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# --------------------------------------------------------------------------
# Page config & light styling
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="Delivery Performance Dashboard",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .metric-card {
            background: #ffffff10;
            border-radius: 10px;
            padding: 1rem;
        }
        div[data-testid="stMetric"] {
            background-color: rgba(128,128,128,0.08);
            border-radius: 10px;
            padding: 12px 16px;
        }
        .block-container { padding-top: 1.5rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------
# Column mapping — normalizes different possible source-column names to a
# single internal schema so the rest of the app doesn't care where the data
# came from.
# --------------------------------------------------------------------------
COLUMN_ALIASES = {
    "order_date": ["order date", "order_date", "orderdate", "order date (dateorders)"],
    "shipping_mode": ["shipping mode", "shipping_mode", "shipmode"],
    "late_delivery_risk": ["late_delivery_risk", "late delivery risk"],
    "days_scheduled": [
        "days for shipment (scheduled)",
        "days_for_shipment_scheduled",
        "scheduled_days",
    ],
    "days_actual": [
        "days for shipping (real)",
        "days_for_shipping_real",
        "actual_days",
    ],
    "region": ["order region", "order_region", "region"],
    "market": ["market", "order_market"],
    "country": ["order country", "order_country", "country"],
    "customer_segment": ["customer segment", "customer_segment", "segment"],
    "order_id": ["order id", "order_id", "order item id", "order_item_id"],
    "sales": ["sales", "order_item_total", "order item total"],
}


def _norm(colname: str) -> str:
    return str(colname).strip().lower()


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map whatever columns exist in df onto our internal schema names."""
    df = df.copy()
    df.columns = [_norm(c) for c in df.columns]
    rename_map = {}
    for internal_name, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in df.columns:
                rename_map[alias] = internal_name
                break
    df = df.rename(columns=rename_map)
    return df


def engineer_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Derive delay_days, on_time flag, order_date as datetime, etc."""
    df = df.copy()

    if "order_date" in df.columns:
        df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")

    if "days_actual" in df.columns and "days_scheduled" in df.columns:
        df["delay_days"] = pd.to_numeric(df["days_actual"], errors="coerce") - pd.to_numeric(
            df["days_scheduled"], errors="coerce"
        )
    elif "delay_days" not in df.columns:
        df["delay_days"] = np.nan

    if "late_delivery_risk" in df.columns:
        df["is_late"] = pd.to_numeric(df["late_delivery_risk"], errors="coerce").fillna(0) > 0
    elif "delay_days" in df.columns:
        df["is_late"] = df["delay_days"] > 0
    else:
        df["is_late"] = False

    return df


REQUIRED_FOR_FULL_FUNCTIONALITY = [
    "order_date",
    "shipping_mode",
    "delay_days",
    "region",
    "market",
    "customer_segment",
]


# --------------------------------------------------------------------------
# Data loaders
# --------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_engine(db_uri: str):
    from sqlalchemy import create_engine

    return create_engine(db_uri)


@st.cache_data(show_spinner="Running query against database...", ttl=300)
def load_from_db(db_uri: str, query: str) -> pd.DataFrame:
    engine = get_engine(db_uri)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df


@st.cache_data(show_spinner=False)
def load_from_upload(file_bytes: bytes, filename: str) -> pd.DataFrame:
    buf = io.BytesIO(file_bytes)
    if filename.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(buf)
    return pd.read_csv(buf)


@st.cache_data(show_spinner=False)
def generate_sample_data(n: int = 6000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    shipping_modes = ["Standard Class", "First Class", "Second Class", "Same Day"]
    mode_weights = [0.55, 0.15, 0.2, 0.1]
    mode_scheduled = {"Standard Class": 6, "First Class": 2, "Second Class": 4, "Same Day": 1}

    region_countries = {
        "Western Europe": ["France", "Germany", "United Kingdom", "Spain", "Italy"],
        "Central America": ["Mexico", "Guatemala", "Honduras", "Costa Rica"],
        "South America": ["Brazil", "Argentina", "Colombia", "Chile", "Peru"],
        "Southeast Asia": ["Indonesia", "Thailand", "Vietnam", "Philippines"],
        "South Asia": ["India", "Pakistan", "Bangladesh", "Sri Lanka"],
        "West Africa": ["Nigeria", "Ghana", "Senegal"],
        "Eastern Africa": ["Kenya", "Ethiopia", "Tanzania"],
        "North America": ["United States", "Canada"],
        "Caribbean": ["Cuba", "Dominican Republic", "Jamaica"],
        "Oceania": ["Australia", "New Zealand"],
    }
    regions = list(region_countries.keys())
    markets = ["Europe", "LATAM", "Pacific Asia", "USCA", "Africa"]
    segments = ["Consumer", "Corporate", "Home Office"]

    dates = pd.date_range("2023-01-01", "2024-12-31", freq="D")

    df = pd.DataFrame(
        {
            "order_id": np.arange(1, n + 1),
            "order_date": rng.choice(dates, size=n),
            "shipping_mode": rng.choice(shipping_modes, size=n, p=mode_weights),
            "region": rng.choice(regions, size=n),
            "market": rng.choice(markets, size=n),
            "customer_segment": rng.choice(segments, size=n, p=[0.5, 0.3, 0.2]),
            "sales": np.round(rng.gamma(shape=2.0, scale=90, size=n), 2),
        }
    )

    df["country"] = [rng.choice(region_countries[r]) for r in df["region"]]
    df["days_scheduled"] = df["shipping_mode"].map(mode_scheduled)
    # actual days = scheduled + noise, with region/mode-dependent delay bias
    region_bias = {r: rng.uniform(-0.3, 1.3) for r in regions}
    noise = rng.normal(loc=df["region"].map(region_bias), scale=1.6)
    df["days_actual"] = np.clip(
        np.round(df["days_scheduled"] + noise).astype(int), 0, None
    )
    df["delay_days"] = df["days_actual"] - df["days_scheduled"]
    df["late_delivery_risk"] = (df["delay_days"] > 0).astype(int)

    return df


# --------------------------------------------------------------------------
# Sidebar — data source selection
# --------------------------------------------------------------------------
st.sidebar.title("🚚 Data Source")

source_type = st.sidebar.radio(
    "Choose a data source",
    ["Sample data (demo)", "Live database", "Upload CSV / Excel"],
    index=0,
)

raw_df = None
load_error = None

if source_type == "Live database":
    st.sidebar.caption("Any SQLAlchemy-compatible URI, e.g. "
                        "`postgresql://user:pass@host:5432/dbname`")
    db_uri = st.sidebar.text_input("Database URI", value="", type="password")
    default_query = "SELECT * FROM orders LIMIT 10000"
    query = st.sidebar.text_area("SQL query", value=default_query, height=100)
    connect_clicked = st.sidebar.button("Connect & load", type="primary")

    if connect_clicked and db_uri:
        try:
            raw_df = load_from_db(db_uri, query)
            st.sidebar.success(f"Loaded {len(raw_df):,} rows.")
        except Exception as e:  # noqa: BLE001
            load_error = str(e)
    elif not db_uri:
        st.sidebar.info("Enter a database URI and click **Connect & load**.")

elif source_type == "Upload CSV / Excel":
    uploaded = st.sidebar.file_uploader("Upload file", type=["csv", "xlsx", "xls"])
    if uploaded is not None:
        try:
            raw_df = load_from_upload(uploaded.getvalue(), uploaded.name)
            st.sidebar.success(f"Loaded {len(raw_df):,} rows.")
        except Exception as e:  # noqa: BLE001
            load_error = str(e)

else:  # Sample data
    raw_df = generate_sample_data()
    st.sidebar.success(f"Loaded {len(raw_df):,} sample rows.")

if load_error:
    st.sidebar.error(f"Failed to load data: {load_error}")

# --------------------------------------------------------------------------
# Stop here if we have no data yet
# --------------------------------------------------------------------------
if raw_df is None or raw_df.empty:
    st.title("🚚 Delivery Performance Dashboard")
    st.info(
        "Pick a data source in the sidebar to get started. Choose "
        "**Sample data (demo)** to preview the dashboard immediately, or "
        "connect a live database / upload a file with your own delivery data."
    )
    st.stop()

# --------------------------------------------------------------------------
# Normalize + engineer
# --------------------------------------------------------------------------
df = normalize_columns(raw_df)
df = engineer_fields(df)

missing_cols = [c for c in REQUIRED_FOR_FULL_FUNCTIONALITY if c not in df.columns]
if missing_cols:
    st.warning(
        "Some expected columns weren't found in your data, so a few charts "
        f"may be limited: `{', '.join(missing_cols)}`. Expected fields include "
        "order date, shipping mode, days for shipment (scheduled), days for "
        "shipping (real) or delay_days, region, market, customer segment."
    )

# --------------------------------------------------------------------------
# Sidebar — filters
# --------------------------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.title("🔎 Filters")


def multiselect_filter(label, col):
    if col in df.columns:
        options = sorted(df[col].dropna().unique().tolist())
        selected = st.sidebar.multiselect(label, options, default=options)
        return selected
    return None


mode_sel = multiselect_filter("Shipping mode", "shipping_mode")
region_sel = multiselect_filter("Region", "region")
market_sel = multiselect_filter("Market", "market")
segment_sel = multiselect_filter("Customer segment", "customer_segment")

date_range = None
if "order_date" in df.columns and df["order_date"].notna().any():
    min_d = df["order_date"].min().date()
    max_d = df["order_date"].max().date()
    date_range = st.sidebar.date_input(
        "Date range", value=(min_d, max_d), min_value=min_d, max_value=max_d
    )

filtered = df.copy()
if mode_sel is not None:
    filtered = filtered[filtered["shipping_mode"].isin(mode_sel)]
if region_sel is not None:
    filtered = filtered[filtered["region"].isin(region_sel)]
if market_sel is not None:
    filtered = filtered[filtered["market"].isin(market_sel)]
if segment_sel is not None:
    filtered = filtered[filtered["customer_segment"].isin(segment_sel)]
if date_range and isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = date_range
    filtered = filtered[
        (filtered["order_date"] >= pd.Timestamp(start))
        & (filtered["order_date"] <= pd.Timestamp(end))
    ]

if filtered.empty:
    st.warning("No rows match the current filters. Try widening your selection.")
    st.stop()


# --------------------------------------------------------------------------
# KPI helpers
# --------------------------------------------------------------------------
def shipping_mode_efficiency(d: pd.DataFrame) -> pd.DataFrame:
    """Shipping Mode Efficiency Index = 100 x (mode on-time rate / overall on-time rate).
    100 = overall average; >100 = more efficient than average."""
    overall_on_time = 1 - d["is_late"].mean()
    g = (
        d.groupby("shipping_mode")
        .agg(orders=("is_late", "size"), late_rate=("is_late", "mean"),
             avg_delay=("delay_days", "mean"))
        .reset_index()
    )
    g["on_time_rate"] = 1 - g["late_rate"]
    g["efficiency_index"] = (
        100 * g["on_time_rate"] / overall_on_time if overall_on_time > 0 else np.nan
    )
    return g


def regional_delay_index(d: pd.DataFrame, col: str) -> pd.DataFrame:
    """Regional Delay Index = 100 x (group late rate / overall late rate).
    100 = overall average; >100 = worse (more delay intensity) than average."""
    overall_late = d["is_late"].mean()
    g = (
        d.groupby(col)
        .agg(orders=("is_late", "size"), late_rate=("is_late", "mean"),
             avg_delay=("delay_days", "mean"))
        .reset_index()
    )
    g["delay_index"] = 100 * g["late_rate"] / overall_late if overall_late > 0 else np.nan
    return g

# --------------------------------------------------------------------------
# Header
# --------------------------------------------------------------------------
st.title("🚚 Delivery Performance Dashboard")
st.caption(
    f"Showing **{len(filtered):,}** of {len(df):,} orders — "
    f"last refreshed {datetime.now().strftime('%Y-%m-%d %H:%M')}"
)

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "📊 Delivery Performance Overview",
        "⚠️ Delay Risk Analysis",
        "🚢 Shipping Mode Comparison",
        "🗺️ Regional & Market Heatmaps",
    ]
)

# --------------------------------------------------------------------------
# TAB 1 — Delivery Performance Overview
# --------------------------------------------------------------------------
with tab1:
    late_ratio = filtered["is_late"].mean()
    on_time_pct = (1 - late_ratio) * 100
    avg_delay = filtered["delay_days"].mean()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("On-Time Delivery Rate", f"{on_time_pct:.1f}%")
    c2.metric("Avg Delivery Delay (days)", f"{avg_delay:.2f}" if pd.notna(avg_delay) else "N/A")
    c3.metric("Late Delivery Risk Ratio", f"{late_ratio:.3f}")
    c4.metric("Total Orders", f"{len(filtered):,}")

    c5, c6, c7, c8 = st.columns(4)
    if "shipping_mode" in filtered.columns:
        me = shipping_mode_efficiency(filtered).sort_values("efficiency_index", ascending=False)
        c5.metric("Most Efficient Mode", me.iloc[0]["shipping_mode"],
                  f"Index {me.iloc[0]['efficiency_index']:.1f}")
        c6.metric("Least Efficient Mode", me.iloc[-1]["shipping_mode"],
                  f"Index {me.iloc[-1]['efficiency_index']:.1f}", delta_color="inverse")
    if "region" in filtered.columns:
        ri = regional_delay_index(filtered, "region").sort_values("delay_index", ascending=False)
        c7.metric("Highest Delay Region", ri.iloc[0]["region"],
                  f"Index {ri.iloc[0]['delay_index']:.1f}", delta_color="inverse")
        c8.metric("Lowest Delay Region", ri.iloc[-1]["region"],
                  f"Index {ri.iloc[-1]['delay_index']:.1f}")

    with st.expander("KPI definitions"):
        st.markdown(
            """
| KPI | Definition |
|---|---|
| **On-Time Delivery Rate (%)** | % of orders delivered within the scheduled time |
| **Average Delivery Delay (Days)** | Mean of (actual − scheduled) shipping days |
| **Late Delivery Risk Ratio** | Proportion of delayed shipments (0–1) |
| **Shipping Mode Efficiency Index** | 100 × mode on-time rate ÷ overall on-time rate (>100 = better than average) |
| **Regional Delay Index** | 100 × region/market late rate ÷ overall late rate (>100 = worse than average) |
            """
        )

    st.markdown("#### Orders over time")
    if "order_date" in filtered.columns:
        trend = (
            filtered.dropna(subset=["order_date"])
            .assign(month=lambda d: d["order_date"].dt.to_period("M").dt.to_timestamp())
            .groupby("month")
            .agg(orders=("order_date", "count"), late_rate=("is_late", "mean"))
            .reset_index()
        )
        fig = px.bar(
            trend, x="month", y="orders",
            title="Monthly Order Volume", labels={"month": "Month", "orders": "Orders"},
        )
        fig2 = px.line(
            trend, x="month", y="late_rate",
            title="Monthly Late-Delivery Rate",
            labels={"month": "Month", "late_rate": "Late rate"},
        )
        fig2.update_yaxes(tickformat=".0%")
        col_a, col_b = st.columns(2)
        col_a.plotly_chart(fig, width="stretch")
        col_b.plotly_chart(fig2, width="stretch")
    else:
        st.info("No `order_date` column available for a trend chart.")

# --------------------------------------------------------------------------
# TAB 2 — Delay Risk Analysis
# --------------------------------------------------------------------------
with tab2:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Late-delivery risk distribution")
        risk_counts = filtered["is_late"].map({True: "Late", False: "On-time"}).value_counts()
        fig = px.pie(
            values=risk_counts.values, names=risk_counts.index, hole=0.45,
            color=risk_counts.index,
            color_discrete_map={"Late": "#EF553B", "On-time": "#00CC96"},
        )
        st.plotly_chart(fig, width="stretch")

    with col2:
        st.markdown("#### Delay gap distribution (actual − scheduled days)")
        if filtered["delay_days"].notna().any():
            fig = px.histogram(
                filtered, x="delay_days", nbins=30,
                labels={"delay_days": "Delay (days)"},
            )
            fig.add_vline(x=0, line_dash="dash", line_color="gray")
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No delay data available.")

    st.markdown("#### Delay risk by customer segment")
    if "customer_segment" in filtered.columns:
        seg = filtered.groupby("customer_segment")["is_late"].mean().reset_index()
        seg["is_late"] = seg["is_late"] * 100
        fig = px.bar(
            seg, x="customer_segment", y="is_late",
            labels={"customer_segment": "Segment", "is_late": "Late rate (%)"},
        )
        st.plotly_chart(fig, width="stretch")

# --------------------------------------------------------------------------
# TAB 3 — Shipping Mode Comparison
# --------------------------------------------------------------------------
with tab3:
    if "shipping_mode" in filtered.columns:
        mode_stats = shipping_mode_efficiency(filtered).sort_values("orders", ascending=False)
        mode_stats["sla_compliance_pct"] = mode_stats["on_time_rate"] * 100
        mode_stats["late_rate_pct"] = mode_stats["late_rate"] * 100

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Late-delivery rate by shipping mode")
            fig = px.bar(
                mode_stats, x="shipping_mode", y="late_rate_pct",
                labels={"shipping_mode": "Mode", "late_rate_pct": "Late rate (%)"},
                color="late_rate_pct", color_continuous_scale="Reds",
            )
            st.plotly_chart(fig, width="stretch")
        with col2:
            st.markdown("#### Average delay by shipping mode")
            fig = px.bar(
                mode_stats, x="shipping_mode", y="avg_delay",
                labels={"shipping_mode": "Mode", "avg_delay": "Avg delay (days)"},
            )
            st.plotly_chart(fig, width="stretch")

        st.markdown("#### Shipping Mode Efficiency Index (100 = overall average)")
        fig = px.bar(
            mode_stats.sort_values("efficiency_index"), x="efficiency_index", y="shipping_mode",
            orientation="h", color="efficiency_index", color_continuous_scale="RdYlGn",
            labels={"efficiency_index": "Efficiency Index", "shipping_mode": "Mode"},
        )
        fig.add_vline(x=100, line_dash="dash", line_color="gray")
        st.plotly_chart(fig, width="stretch")

        st.markdown("#### SLA compliance table")
        st.dataframe(
            mode_stats[["shipping_mode", "orders", "sla_compliance_pct", "avg_delay", "efficiency_index"]]
            .rename(
                columns={
                    "shipping_mode": "Shipping Mode",
                    "orders": "Orders",
                    "sla_compliance_pct": "SLA Compliance (%)",
                    "avg_delay": "Avg Delay (days)",
                    "efficiency_index": "Efficiency Index",
                }
            )
            .round(2),
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("No `shipping_mode` column available.")

# --------------------------------------------------------------------------
# TAB 4 — Regional & Market Heatmaps
# --------------------------------------------------------------------------
with tab4:
    if "region" in filtered.columns and "market" in filtered.columns:
        heat = (
            filtered.groupby(["market", "region"])["is_late"]
            .mean()
            .reset_index()
        )
        heat["is_late"] = heat["is_late"] * 100
        pivot = heat.pivot(index="region", columns="market", values="is_late")

        st.markdown("#### Late-delivery rate — Region × Market (%)")
        fig = px.imshow(
            pivot,
            color_continuous_scale="RdYlGn_r",
            aspect="auto",
            labels=dict(color="Late rate (%)"),
        )
        st.plotly_chart(fig, width="stretch")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Regional Delay Index (100 = overall average)")
            reg = regional_delay_index(filtered, "region").sort_values("delay_index")
            fig = px.bar(
                reg, x="delay_index", y="region", orientation="h",
                labels={"delay_index": "Delay Index", "region": "Region"},
                color="delay_index", color_continuous_scale="RdYlGn_r",
            )
            fig.add_vline(x=100, line_dash="dash", line_color="gray")
            st.plotly_chart(fig, width="stretch")
        with col2:
            st.markdown("#### Market-wise logistics efficiency")
            mkt = regional_delay_index(filtered, "market").sort_values("delay_index")
            mkt["on_time_pct"] = (1 - mkt["late_rate"]) * 100
            fig = px.bar(
                mkt, x="market", y="on_time_pct",
                hover_data=["orders", "avg_delay", "delay_index"],
                labels={"market": "Market", "on_time_pct": "On-time rate (%)"},
                color="delay_index", color_continuous_scale="RdYlGn_r",
            )
            st.plotly_chart(fig, width="stretch")

        if "country" in filtered.columns:
            st.markdown("#### Geographic delay visualization (late rate by country)")
            geo = regional_delay_index(filtered, "country")
            geo["late_rate_pct"] = geo["late_rate"] * 100
            fig = px.choropleth(
                geo, locations="country", locationmode="country names",
                color="late_rate_pct", hover_data=["orders", "avg_delay", "delay_index"],
                color_continuous_scale="RdYlGn_r",
                labels={"late_rate_pct": "Late rate (%)"},
            )
            fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig, width="stretch")
        else:
            st.caption("Add an `order country` / `country` column to enable the world map.")
    else:
        st.info("No `region`/`market` columns available for the heatmap.")

st.markdown("---")
with st.expander("Preview filtered data"):
    st.dataframe(filtered.head(200), width="stretch")
