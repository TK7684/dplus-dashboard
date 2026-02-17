"""
DuckDB database module for DPLUS Dashboard.
High-performance SQL analytics for large datasets.
"""

import os
import glob
import duckdb
import pandas as pd
import streamlit as st
from typing import Optional, Tuple, List
from datetime import date, datetime

# Configuration
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_ROOT, 'dplus.duckdb')

# Data directories to check
DATA_DIRS = [
    os.path.join(PROJECT_ROOT, 'Original files'),
    os.path.join(PROJECT_ROOT, 'data'),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploaded'),
]

# Blacklist keywords (case-insensitive)
BLACKLIST_KEYWORDS = [
    'apple', 'iphone', 'ipad', 'macbook', 'airpods', 'apple watch',
    'samsung', 'galaxy', 'case', 'charger', 'cable', 'headphone',
    'earphone', 'earbuds', 'electronics', 'accessories', 'adapter',
    'tempered glass', 'screen protector', 'phone cover', 'phone case',
    'wireless charger', 'power bank', 'usb', 'lightning', 'type-c'
]


def get_connection() -> duckdb.DuckDBPyConnection:
    """Get DuckDB connection with optimized settings."""
    conn = duckdb.connect(DB_PATH, read_only=False)
    # Performance optimizations
    conn.execute("SET threads=4")
    conn.execute("SET memory_limit='2GB'")
    return conn


def init_database():
    """Initialize the DuckDB database with optimized schema."""
    conn = get_connection()

    # Create orders table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            order_id VARCHAR,
            platform VARCHAR,
            product_name VARCHAR,
            quantity INTEGER,
            subtotal_net DOUBLE,
            order_total_amount DOUBLE,
            created_at TIMESTAMP,
            date DATE,
            seller_sku VARCHAR,
            order_status VARCHAR,
            product_category VARCHAR
        )
    ''')

    # Create indexes for fast querying
    conn.execute("CREATE INDEX IF NOT EXISTS idx_date ON orders(date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_platform ON orders(platform)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_order_id ON orders(order_id)")

    # Create metadata table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS loaded_files (
            filename VARCHAR PRIMARY KEY,
            file_mtime DOUBLE,
            rows_loaded INTEGER,
            loaded_at TIMESTAMP
        )
    ''')

    conn.close()


def get_loaded_files() -> set:
    """Get set of already loaded files."""
    conn = get_connection()
    try:
        result = conn.execute("SELECT filename FROM loaded_files").fetchall()
        return {row[0] for row in result}
    except:
        return set()
    finally:
        conn.close()


def is_blacklisted(product_name: str) -> bool:
    """Check if product should be excluded."""
    if not product_name or pd.isna(product_name):
        return False
    product_lower = str(product_name).lower()
    return any(kw in product_lower for kw in BLACKLIST_KEYWORDS)


def load_tiktok_file(filepath: str, conn) -> int:
    """Load TikTok CSV/CSV.GZ file into DuckDB."""
    filename = os.path.basename(filepath)

    # Read CSV (handles gzip automatically)
    try:
        df = pd.read_csv(filepath, encoding='utf-8', low_memory=False)
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(filepath, encoding='utf-8-sig', low_memory=False)
        except:
            df = pd.read_csv(filepath, encoding='latin-1', low_memory=False)

    df.columns = df.columns.str.strip()

    if 'Product Name' not in df.columns or 'Order ID' not in df.columns:
        return 0

    # Filter blacklisted products
    df = df[~df['Product Name'].fillna('').apply(is_blacklisted)]
    if df.empty:
        return 0

    # Parse dates
    df['created_at_dt'] = pd.to_datetime(df['Created Time'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
    if df['created_at_dt'].isna().all():
        df['created_at_dt'] = pd.to_datetime(df['Created Time'], dayfirst=True, errors='coerce')

    df = df[df['created_at_dt'].notna()]
    if df.empty:
        return 0

    # Prepare data
    df['order_id'] = df['Order ID'].astype(str).str.strip()
    df['product_name'] = df['Product Name'].astype(str).str.strip().str[:500]
    df['quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(0).clip(lower=0).astype(int)
    df['subtotal_net'] = pd.to_numeric(df['SKU Subtotal After Discount'], errors='coerce').fillna(0).clip(lower=0)
    df['order_total_amount'] = pd.to_numeric(df['Order Amount'], errors='coerce').fillna(0).clip(lower=0)
    df['seller_sku'] = df.get('Seller SKU', '').astype(str).str.strip()
    df['order_status'] = df.get('Order Status', '').astype(str).str.strip()
    df['product_category'] = df.get('Product Category', '').astype(str).str.strip()
    df['platform'] = 'TikTok'
    df['date'] = df['created_at_dt'].dt.date

    # Remove empty order_ids
    df = df[df['order_id'] != '']
    if df.empty:
        return 0

    # Select final columns
    final_df = df[[
        'order_id', 'platform', 'product_name', 'quantity',
        'subtotal_net', 'order_total_amount', 'created_at_dt',
        'date', 'seller_sku', 'order_status', 'product_category'
    ]].copy()
    final_df.columns = [
        'order_id', 'platform', 'product_name', 'quantity',
        'subtotal_net', 'order_total_amount', 'created_at',
        'date', 'seller_sku', 'order_status', 'product_category'
    ]

    # Delete existing records for these orders (to handle updates)
    order_ids = df['order_id'].unique().tolist()
    if order_ids:
        placeholders = ','.join(['?'] * len(order_ids))
        conn.execute(f"DELETE FROM orders WHERE order_id IN ({placeholders}) AND platform = 'TikTok'", order_ids)

    # Insert new records
    conn.execute("INSERT INTO orders SELECT * FROM final_df")

    # Mark file as loaded
    conn.execute("""
        INSERT OR REPLACE INTO loaded_files (filename, file_mtime, rows_loaded, loaded_at)
        VALUES (?, ?, ?, NOW())
    """, [filename, os.path.getmtime(filepath), len(final_df)])

    return len(final_df)


def load_shopee_file(filepath: str, conn) -> int:
    """Load Shopee Excel file into DuckDB."""
    filename = os.path.basename(filepath)

    df = pd.read_excel(filepath)

    product_col = 'ชื่อสินค้า'
    order_col = 'หมายเลขคำสั่งซื้อ'

    if product_col not in df.columns or order_col not in df.columns:
        return 0

    # Filter blacklisted products
    df = df[~df[product_col].fillna('').apply(is_blacklisted)]
    if df.empty:
        return 0

    # Parse dates
    df['created_at_dt'] = pd.to_datetime(df['วันที่ทำการสั่งซื้อ'], errors='coerce')
    if df['created_at_dt'].isna().all():
        df['created_at_dt'] = pd.to_datetime(df['วันที่ทำการสั่งซื้อ'], dayfirst=True, errors='coerce')

    df = df[df['created_at_dt'].notna()]
    if df.empty:
        return 0

    # Prepare data
    df['order_id'] = df[order_col].astype(str).str.strip()
    df['product_name'] = df[product_col].astype(str).str.strip().str[:500]
    df['quantity'] = pd.to_numeric(df['จำนวน'], errors='coerce').fillna(0).clip(lower=0).astype(int)
    df['subtotal_net'] = pd.to_numeric(df['ราคาขายสุทธิ'], errors='coerce').fillna(0).clip(lower=0)
    df['order_total_amount'] = pd.to_numeric(df['จำนวนเงินทั้งหมด'], errors='coerce').fillna(0).clip(lower=0)
    df['seller_sku'] = df.get('เลขอ้างอิง SKU (SKU Reference No.)', '').astype(str).str.strip()
    df['order_status'] = df.get('สถานะการสั่งซื้อ', '').astype(str).str.strip()
    df['product_category'] = ''
    df['platform'] = 'Shopee'
    df['date'] = df['created_at_dt'].dt.date

    # Remove empty order_ids
    df = df[df['order_id'] != '']
    if df.empty:
        return 0

    # Select final columns
    final_df = df[[
        'order_id', 'platform', 'product_name', 'quantity',
        'subtotal_net', 'order_total_amount', 'created_at_dt',
        'date', 'seller_sku', 'order_status', 'product_category'
    ]].copy()
    final_df.columns = [
        'order_id', 'platform', 'product_name', 'quantity',
        'subtotal_net', 'order_total_amount', 'created_at',
        'date', 'seller_sku', 'order_status', 'product_category'
    ]

    # Delete existing records for these orders
    order_ids = df['order_id'].unique().tolist()
    if order_ids:
        placeholders = ','.join(['?'] * len(order_ids))
        conn.execute(f"DELETE FROM orders WHERE order_id IN ({placeholders}) AND platform = 'Shopee'", order_ids)

    # Insert new records
    conn.execute("INSERT INTO orders SELECT * FROM final_df")

    # Mark file as loaded
    conn.execute("""
        INSERT OR REPLACE INTO loaded_files (filename, file_mtime, rows_loaded, loaded_at)
        VALUES (?, ?, ?, NOW())
    """, [filename, os.path.getmtime(filepath), len(final_df)])

    return len(final_df)


@st.cache_resource
def build_database(show_progress=True) -> bool:
    """Build the DuckDB database from source files."""
    init_database()
    conn = get_connection()

    loaded_files = get_loaded_files()

    # Find all data files
    all_files = []
    for data_dir in DATA_DIRS:
        if os.path.exists(data_dir):
            # TikTok files (CSV and CSV.GZ)
            all_files.extend(glob.glob(os.path.join(data_dir, '*.csv')))
            all_files.extend(glob.glob(os.path.join(data_dir, '*.csv.gz')))
            # Shopee files
            all_files.extend(glob.glob(os.path.join(data_dir, '*.xlsx')))

    # Filter to new files only
    new_files = [f for f in all_files if os.path.basename(f) not in loaded_files]

    if not new_files:
        conn.close()
        return True

    total_rows = 0
    total_files = len(new_files)

    for i, filepath in enumerate(new_files):
        filename = os.path.basename(filepath)

        if filepath.endswith('.csv') or filepath.endswith('.csv.gz'):
            rows = load_tiktok_file(filepath, conn)
        elif filepath.endswith('.xlsx'):
            rows = load_shopee_file(filepath, conn)
        else:
            rows = 0

        total_rows += rows

        if show_progress and (i + 1) % 5 == 0:
            print(f"[DuckDB] Loaded {i + 1}/{total_files} files, {total_rows:,} rows")

    conn.close()

    if total_rows > 0:
        print(f"[DuckDB] Total: {total_rows:,} rows from {total_files} files")

    return True


def refresh_database() -> int:
    """Refresh database by loading new files."""
    return build_database(show_progress=False) or 0


def get_new_files_count() -> int:
    """Get count of new files not yet loaded."""
    loaded_files = get_loaded_files()

    count = 0
    for data_dir in DATA_DIRS:
        if os.path.exists(data_dir):
            for pattern in ['*.csv', '*.csv.gz', '*.xlsx']:
                for f in glob.glob(os.path.join(data_dir, pattern)):
                    if os.path.basename(f) not in loaded_files:
                        count += 1

    return count


# =============================================================================
# Query Functions
# =============================================================================

def query_revenue_by_period(
    start_date: date,
    end_date: date,
    granularity: str = 'D',
    platform: str = 'All',
    compare_start: date = None,
    compare_end: date = None
) -> pd.DataFrame:
    """Query revenue data aggregated by time period."""
    if granularity == 'D':
        group_expr = 'date'
    elif granularity == 'W':
        group_expr = "DATE_TRUNC('week', date)"
    elif granularity == 'M':
        group_expr = "DATE_TRUNC('month', date)"
    else:
        group_expr = "DATE_TRUNC('quarter', date)"

    platform_filter = "" if platform == 'All' else f"AND platform = '{platform}'"

    query = f'''
        SELECT
            {group_expr} as period,
            platform,
            SUM(subtotal_net) as revenue,
            COUNT(DISTINCT order_id) as orders,
            SUM(quantity) as quantity,
            'current' as period_type
        FROM orders
        WHERE date >= ? AND date <= ? {platform_filter}
        GROUP BY {group_expr}, platform
        ORDER BY period
    '''

    conn = get_connection()
    try:
        df = conn.execute(query, [start_date, end_date]).fetchdf()

        if compare_start and compare_end:
            df_compare = conn.execute(query, [compare_start, compare_end]).fetchdf()
            df_compare['period_type'] = 'previous'
            df = pd.concat([df, df_compare], ignore_index=True)

        return df
    finally:
        conn.close()


def query_aov_by_period(
    start_date: date,
    end_date: date,
    granularity: str = 'D',
    platform: str = 'All',
    compare_start: date = None,
    compare_end: date = None
) -> pd.DataFrame:
    """Query AOV data by period."""
    if granularity == 'D':
        group_expr = 'date'
    elif granularity == 'W':
        group_expr = "DATE_TRUNC('week', date)"
    elif granularity == 'M':
        group_expr = "DATE_TRUNC('month', date)"
    else:
        group_expr = "DATE_TRUNC('quarter', date)"

    platform_filter = "" if platform == 'All' else f"AND platform = '{platform}'"

    query = f'''
        SELECT
            {group_expr} as period,
            platform,
            SUM(subtotal_net) as revenue,
            COUNT(DISTINCT order_id) as orders,
            SUM(subtotal_net) * 1.0 / COUNT(DISTINCT order_id) as aov,
            'current' as period_type
        FROM orders
        WHERE date >= ? AND date <= ? {platform_filter}
        GROUP BY {group_expr}, platform
        ORDER BY period
    '''

    conn = get_connection()
    try:
        df = conn.execute(query, [start_date, end_date]).fetchdf()

        if compare_start and compare_end:
            df_compare = conn.execute(query, [compare_start, compare_end]).fetchdf()
            df_compare['period_type'] = 'previous'
            df = pd.concat([df, df_compare], ignore_index=True)

        return df
    finally:
        conn.close()


def query_product_stats(
    start_date: date,
    end_date: date,
    platform: str = 'All',
    compare_start: date = None,
    compare_end: date = None
) -> pd.DataFrame:
    """Query product statistics."""
    platform_filter = "" if platform == 'All' else f"AND platform = '{platform}'"

    query = f'''
        SELECT
            product_name,
            platform,
            SUM(subtotal_net) as revenue,
            SUM(quantity) as quantity,
            COUNT(DISTINCT order_id) as orders,
            'current' as period_type
        FROM orders
        WHERE date >= ? AND date <= ? {platform_filter}
        GROUP BY product_name, platform
        ORDER BY revenue DESC
    '''

    conn = get_connection()
    try:
        df = conn.execute(query, [start_date, end_date]).fetchdf()

        if compare_start and compare_end:
            df_compare = conn.execute(query, [compare_start, compare_end]).fetchdf()
            df_compare['period_type'] = 'previous'
            df = pd.concat([df, df_compare], ignore_index=True)

        return df
    finally:
        conn.close()


def query_summary_metrics(
    start_date: date,
    end_date: date,
    platform: str = 'All'
) -> dict:
    """Query summary metrics for a period."""
    platform_filter = "" if platform == 'All' else f"AND platform = '{platform}'"

    query = f'''
        SELECT
            COUNT(DISTINCT order_id) as total_orders,
            COALESCE(SUM(subtotal_net), 0) as total_revenue,
            COALESCE(SUM(quantity), 0) as total_quantity,
            CASE
                WHEN COUNT(DISTINCT order_id) > 0
                THEN SUM(subtotal_net) * 1.0 / COUNT(DISTINCT order_id)
                ELSE 0
            END as aov,
            COUNT(DISTINCT product_name) as unique_products
        FROM orders
        WHERE date >= ? AND date <= ? {platform_filter}
    '''

    conn = get_connection()
    try:
        result = conn.execute(query, [start_date, end_date]).fetchone()
        if result:
            return {
                'total_orders': result[0] or 0,
                'total_revenue': result[1] or 0,
                'total_quantity': result[2] or 0,
                'aov': result[3] or 0,
                'unique_products': result[4] or 0
            }
        return {'total_orders': 0, 'total_revenue': 0, 'total_quantity': 0, 'aov': 0, 'unique_products': 0}
    finally:
        conn.close()


def query_date_range() -> Tuple[date, date]:
    """Get the min and max dates in the database."""
    conn = get_connection()
    try:
        result = conn.execute("SELECT MIN(date), MAX(date) FROM orders").fetchone()
        if result[0] and result[1]:
            return result[0], result[1]
        return date.today(), date.today()
    except:
        return date.today(), date.today()
    finally:
        conn.close()


def get_db_stats() -> dict:
    """Get database statistics."""
    conn = get_connection()
    try:
        total_rows = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        unique_orders = conn.execute("SELECT COUNT(DISTINCT order_id) FROM orders").fetchone()[0]
        unique_products = conn.execute("SELECT COUNT(DISTINCT product_name) FROM orders").fetchone()[0]

        by_platform = {}
        result = conn.execute("SELECT platform, COUNT(*) FROM orders GROUP BY platform").fetchall()
        for row in result:
            by_platform[row[0]] = row[1]

        return {
            'total_rows': total_rows,
            'unique_orders': unique_orders,
            'unique_products': unique_products,
            'by_platform': by_platform
        }
    except:
        return {'total_rows': 0, 'unique_orders': 0, 'unique_products': 0, 'by_platform': {}}
    finally:
        conn.close()


def is_database_empty() -> bool:
    """Check if database has no data."""
    conn = get_connection()
    try:
        count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        return count == 0
    except:
        return True
    finally:
        conn.close()


def load_multiple_uploaded_files(uploaded_files) -> int:
    """Load uploaded files into database."""
    import tempfile

    init_database()
    conn = get_connection()
    total_rows = 0

    for uploaded_file in uploaded_files:
        suffix = os.path.splitext(uploaded_file.name)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name

        try:
            if suffix in ['.csv', '.gz']:
                rows = load_tiktok_file(tmp_path, conn)
            elif suffix == '.xlsx':
                rows = load_shopee_file(tmp_path, conn)
            else:
                rows = 0
            total_rows += rows
        finally:
            os.unlink(tmp_path)

    conn.close()
    return total_rows
