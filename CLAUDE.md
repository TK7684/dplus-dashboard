# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

D Plus Skin Analytics is a Streamlit-based performance dashboard for skincare & wellness businesses. It tracks sales data from TikTok and Shopee platforms with revenue trends, AOV analysis, product matrix visualization, and portfolio health monitoring.

## Run Commands

```bash
# Start the dashboard
streamlit run src/app.py

# Install dependencies
pip install -r requirements.txt

# Rebuild database (delete and reload)
rm -f dplus.duckdb dplus.duckdb.wal && python -c "from src.data.database import build_database; build_database()"
```

## Architecture

### Data Flow
```
Source Files (Original files/)
    ↓
File Monitor (watchdog) → Data Loader → Data Cleaner → DuckDB Database
    ↓
Query Functions → Streamlit Components (charts/tables)
```

### Key Modules

| Path | Purpose |
|------|---------|
| `src/app.py` | Main Streamlit application entry point |
| `src/data/database.py` | DuckDB database module with all query functions |
| `src/data/loader.py` | TikTok CSV / Shopee Excel file loading |
| `src/data/cleaner.py` | Data cleaning pipeline (dates, deduplication) |
| `src/data/validation.py` | Data integrity validation before/after operations |
| `src/analytics/super_query.py` | Min/Middle/Max segmentation analytics |
| `src/components/` | UI components (revenue_chart, aov_chart, product_matrix, portfolio_health, sidebar) |

### Database (DuckDB)

- **Location**: `dplus.duckdb` (persistent file)
- **Main table**: `orders` (55+ columns including order_id, platform, product_name, subtotal_net, created_at, date)
- **Deduplication**: By `order_id + platform` combination
- **Timezone**: All timestamps localized to `Asia/Bangkok`

### Data File Patterns

| Platform | Pattern | Format |
|----------|---------|--------|
| TikTok | `ทั้งหมด คำสั่งซื้อ-*.csv` | CSV (DD/MM/YYYY HH:MM:SS) |
| Shopee | `Order.all.*.xlsx` | Excel (YYYY-MM-DD HH:MM) |

Files go in `Original files/` directory.

### Segmentation Logic (Min/Middle/Max)

- **Revenue**: Top 20% = Max, Bottom 20% = Min, Rest = Middle
- **AOV**: >1.2x avg = Max, <0.8x avg = Min
- **Products**: Top 67% revenue = Hero (Max), High qty/low revenue = Volume (Min)

### Color Palette (config.py)

```python
COLORS = {
    'Max': '#10B981',      # Emerald green
    'Middle': '#6366F1',   # Indigo
    'Min': '#F97316',      # Orange
    'TikTok': '#1E293B',   # Slate dark
    'Shopee': '#EF4444',   # Coral red
    'Primary': '#4A7C6F',  # Sage green
}
```

## Important Patterns

### Adding New Query Functions

Add to `src/data/database.py` following the existing pattern:
1. Use `get_connection()` to get DuckDB connection
2. Build SQL with `?` placeholders for parameters
3. Return pandas DataFrame via `.fetchdf()`

### Adding New Charts

1. Create component in `src/components/`
2. Import and render in `src/app.py` main function
3. Use plotly for interactive charts
4. Apply color palette from `config.py`

### Time Comparisons

Use `get_comparison_periods()` and `query_platform_comparison()` for:
- DOD (day-over-day), WOW (week-over-week), MOM (month-over-month)
- QOQ_CONSECUTIVE, QOQ_SEQUENTIAL, QOQ_YOY

### Data Validation

Before database updates, use `DataValidator` from `validation.py`:
- `validate_order_uniqueness()` - Check for duplicates
- `validate_before_update()` - Check for data loss
- `check_database_integrity()` - Full database check

## Blacklist Filtering

Products containing these keywords are excluded: apple, iphone, ipad, macbook, airpods, samsung, galaxy, case, charger, cable, headphone, earphone, earbuds, electronics, accessories, adapter, tempered glass, screen protector, phone cover, phone case, wireless charger, power bank, usb, lightning, type-c

## Password

Default dashboard password: `dplus2024` (SHA1 hash stored in `app.py`)
