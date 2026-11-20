# Delivery Performance Dashboard

A Streamlit dashboard for delivery/logistics performance analysis.

## Modules
- **Delivery Performance Overview** — on-time vs. late KPIs, avg delay, monthly trend
- **Delay Risk Analysis** — late-delivery risk distribution, delay-gap histogram, delay by segment
- **Shipping Mode Comparison** — mode-wise delay performance, SLA compliance table
- **Regional & Market Heatmaps** — region × market delay heatmap, delay by region, volume by market

## Filters (sidebar)
Shipping mode · Region · Market · Customer segment · Date range

## Setup

```bash
pip install -r requirements.txt
streamlit run dashboard.py
```

## Connecting a live data source

In the sidebar, choose **Live database** and enter any SQLAlchemy connection URI, e.g.:

```
postgresql://user:password@host:5432/dbname
mysql+pymysql://user:password@host:3306/dbname
sqlite:///local_data.db
```

Install the matching driver first (see `requirements.txt` for suggestions), then
enter/edit the SQL query in the sidebar (default: `SELECT * FROM orders LIMIT 10000`)
and click **Connect & load**.

Alternatively, choose **Upload CSV / Excel** to load a local file, or **Sample data
(demo)** to preview the dashboard instantly with generated data.

## Expected columns

The app auto-detects common column-name variants (case-insensitive) and maps them
to an internal schema. It works best with a DataCo-style supply-chain schema:

| Internal field       | Recognized source column names                                   |
|-----------------------|--------------------------------------------------------------------|
| `order_date`          | `order date`, `order_date`, `order date (dateorders)`             |
| `shipping_mode`       | `shipping mode`, `shipping_mode`                                   |
| `late_delivery_risk`  | `late_delivery_risk`, `late delivery risk`                         |
| `days_scheduled`      | `days for shipment (scheduled)`                                    |
| `days_actual`         | `days for shipping (real)`                                         |
| `region`               | `order region`, `region`                                            |
| `market`               | `market`                                                             |
| `customer_segment`    | `customer segment`, `segment`                                      |
| `sales`                 | `sales`, `order item total`                                        |

If your columns don't match, either rename them before loading, or add the
alias to `COLUMN_ALIASES` at the top of `dashboard.py`. Missing columns degrade
gracefully — related charts are skipped with a note instead of erroring out.

## KPIs

| KPI | Definition |
|---|---|
| On-Time Delivery Rate (%) | % of orders delivered within scheduled time |
| Average Delivery Delay (Days) | Mean of (actual − scheduled) shipping days |
| Late Delivery Risk Ratio | Proportion of delayed shipments (0–1) |
| Shipping Mode Efficiency Index | 100 × mode on-time rate ÷ overall on-time rate (>100 = better than average) |
| Regional Delay Index | 100 × region/market late rate ÷ overall late rate (>100 = worse than average) |

The world map in the Regional & Market tab appears when the data has an `order country` / `country` column.
