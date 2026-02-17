# D Plus Skin Analytics

Skincare & Wellness Performance Dashboard with revenue trends, AOV analysis, and product matrix visualization.

## Quick Start

```cmd
cd C:\Projects\DPLUS-Dashboard
streamlit run src/app.py
```

## Data Files

Place your data files in the `Original files` folder:
- **TikTok:** `ทั้งหมด คำสั่งซื้อ-*.csv` or `*.csv.gz`
- **Shopee:** `Order.all.*.xlsx`

## Features

- DuckDB for fast analytics (queries files directly)
- Revenue tracking by platform (TikTok/Shopee)
- AOV (Average Order Value) analysis
- Product performance matrix
- Date range filtering and comparison

## Data Filtering

Products containing these keywords are automatically excluded:
apple, iphone, ipad, samsung, galaxy, case, charger, cable, headphone, etc.

## Password

Default password: `dplus2024`
