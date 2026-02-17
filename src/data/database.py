"""
DuckDB direct query module for DPLUS Dashboard.
Queries CSV/XLSX files directly - no database loading required.
This is the fastest approach for large datasets.
"""

import os
import glob
import duckdb
import pandas as pd
import streamlit as st
from typing import Optional, Tuple
from datetime import date

# Configuration
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Data directories to check
DATA_DIRS = [
    os.path.join(PROJECT_ROOT, 'data'),
    os.path.join(PROJECT_ROOT, 'Original files'),
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

# Cache for file discovery
_files_cache = None
_conn_cache = None


def get_data_files() -> dict:
    """Get all data files organized by type."""
    global _files_cache
    if _files_cache is not None:
        return _files_cache

    tiktok_files = []
    shopee_files = []

    for data_dir in DATA_DIRS:
        if os.path.exists(data_dir):
            tiktok_files.extend(glob.glob(os.path.join(data_dir, '*.csv')))
            tiktok_files.extend(glob.glob(os.path.join(data_dir, '*.csv.gz')))
            shopee_files.extend(glob.glob(os.path.join(data_dir, '*.xlsx')))

    _files_cache = {'tiktok': tiktok_files, 'shopee': shopee_files}
    return _files_cache


def build_blacklist_sql() -> str:
    """Generate SQL for blacklist filtering."""
    conditions = [f"LOWER(product_name) NOT LIKE '%{kw}%'" for kw in BLACKLIST_KEYWORDS]
    return " AND ".join(conditions)


@st.cache_resource
def init_database():
    """Initialize DuckDB with views pointing to data files."""
    global _conn_cache
    if _conn_cache is not None:
        return _conn_cache

    conn = duckdb.connect(':memory:')
    conn.execute("SET threads=4")
    conn.execute("SET memory_limit='2GB'")

    # Load TikTok data
    tiktok_files = get_data_files()['tiktok']
    if tiktok_files:
        file_list = ", ".join([f"'{f}'" for f in tiktok_files])
        blacklist_sql = build_blacklist_sql().replace('product_name', 'TRIM("Product Name")')

        conn.execute(f"""
            CREATE OR REPLACE VIEW tiktok_orders AS
            SELECT
                TRIM("Order ID")::VARCHAR as order_id,
                'TikTok' as platform,
                TRIM("Product Name")::VARCHAR as product_name,
                TRY_CAST(TRIM("Quantity") AS INTEGER) as quantity,
                TRY_CAST(TRIM("SKU Subtotal After Discount") AS DOUBLE) as subtotal_net,
                TRY_CAST(TRIM("Order Amount") AS DOUBLE) as order_total_amount,
                TRY_CAST(STRPTIME(TRIM("Created Time"), '%d/%m/%Y %H:%M:%S') AS TIMESTAMP) as created_at,
                TRY_CAST(STRPTIME(SUBSTRING(TRIM("Created Time"), 1, 10), '%d/%m/%Y') AS DATE) as date,
                COALESCE(TRIM("Seller SKU")::VARCHAR, '') as seller_sku,
                COALESCE(TRIM("Order Status")::VARCHAR, '') as order_status,
                COALESCE(TRIM("Product Category")::VARCHAR, '') as product_category
            FROM read_csv_auto(
                [{file_list}],
                header=true,
                ignore_errors=true,
                all_varchar=true
            )
            WHERE "Order ID" IS NOT NULL AND "Order ID" != ''
              AND {blacklist_sql}
        """)

    # Load Shopee data via pandas
    shopee_files = get_data_files()['shopee']
    if shopee_files:
        dfs = []
        for f in shopee_files:
            try:
                df = pd.read_excel(f)
                dfs.append(df)
            except:
                pass

        if dfs:
            shopee_df = pd.concat(dfs, ignore_index=True)

            column_map = {
                'หมายเลขคำสั่งซื้อ': 'order_id',
                'ชื่อสินค้า': 'product_name',
                'จำนวน': 'quantity',
                'ราคาขายสุทธิ': 'subtotal_net',
                'จำนวนเงินทั้งหมด': 'order_total_amount',
                'วันที่ทำการสั่งซื้อ': 'created_at',
                'เลขอ้างอิง SKU (SKU Reference No.)': 'seller_sku',
                'สถานะการสั่งซื้อ': 'order_status'
            }
            shopee_df = shopee_df.rename(columns=column_map)

            mask = ~shopee_df['product_name'].fillna('').str.lower().apply(
                lambda x: any(kw in x for kw in BLACKLIST_KEYWORDS)
            )
            shopee_df = shopee_df[mask]

            shopee_df['platform'] = 'Shopee'
            shopee_df['date'] = pd.to_datetime(shopee_df['created_at'], errors='coerce').dt.date
            shopee_df['product_category'] = ''
            shopee_df['quantity'] = pd.to_numeric(shopee_df['quantity'], errors='coerce').fillna(0).clip(lower=0).astype(int)
            shopee_df['subtotal_net'] = pd.to_numeric(shopee_df['subtotal_net'], errors='coerce').fillna(0).clip(lower=0)
            shopee_df['order_total_amount'] = pd.to_numeric(shopee_df['order_total_amount'], errors='coerce').fillna(0).clip(lower=0)

            # Register DataFrame as a table in DuckDB
            conn.register('shopee_df', shopee_df)
            conn.execute("""
                CREATE OR REPLACE VIEW shopee_orders AS
                SELECT order_id, platform, product_name, quantity,
                       subtotal_net, order_total_amount, created_at, date,
                       seller_sku, order_status, product_category
                FROM shopee_df
            """)

    # Create combined orders view
    has_tiktok = len(get_data_files()['tiktok']) > 0
    has_shopee = len(get_data_files()['shopee']) > 0

    if has_tiktok and has_shopee:
        conn.execute("""
            CREATE OR REPLACE VIEW orders AS
            SELECT order_id, platform, product_name, quantity,
                   subtotal_net, order_total_amount, created_at, date,
                   seller_sku, order_status, product_category
            FROM tiktok_orders
            UNION ALL
            SELECT order_id, platform, product_name, quantity,
                   subtotal_net, order_total_amount, created_at, date,
                   seller_sku, order_status, product_category
            FROM shopee_orders
        """)
    elif has_tiktok:
        conn.execute("CREATE OR REPLACE VIEW orders AS SELECT * FROM tiktok_orders")
    elif has_shopee:
        conn.execute("CREATE OR REPLACE VIEW orders AS SELECT * FROM shopee_orders")
    else:
        # Create empty orders table
        conn.execute("""
            CREATE OR REPLACE VIEW orders AS
            SELECT '' as order_id, '' as platform, '' as product_name,
                   0 as quantity, 0.0 as subtotal_net, 0.0 as order_total_amount,
                   NULL as created_at, NULL as date, '' as seller_sku,
                   '' as order_status, '' as product_category
            WHERE 1=0
        """)

    _conn_cache = conn
    return conn


@st.cache_resource
def build_database(show_progress=True) -> bool:
    """Initialize the database views."""
    try:
        conn = init_database()
        count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        if count > 0:
            print(f"[DuckDB] Direct query ready: {count:,} records")
        return True
    except Exception as e:
        print(f"[DuckDB] Error: {e}")
        return False


def refresh_database() -> int:
    """Refresh by clearing cache and rebuilding."""
    global _files_cache, _conn_cache
    _files_cache = None
    _conn_cache = None
    st.cache_resource.clear()
    return build_database(show_progress=False) or 0


def get_new_files_count() -> int:
    return 0


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
    conn = init_database()

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

    df = conn.execute(query, [start_date, end_date]).fetchdf()

    if compare_start and compare_end:
        df_compare = conn.execute(query, [compare_start, compare_end]).fetchdf()
        df_compare['period_type'] = 'previous'
        df = pd.concat([df, df_compare], ignore_index=True)

    return df


def query_aov_by_period(
    start_date: date,
    end_date: date,
    granularity: str = 'D',
    platform: str = 'All',
    compare_start: date = None,
    compare_end: date = None
) -> pd.DataFrame:
    conn = init_database()

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

    df = conn.execute(query, [start_date, end_date]).fetchdf()

    if compare_start and compare_end:
        df_compare = conn.execute(query, [compare_start, compare_end]).fetchdf()
        df_compare['period_type'] = 'previous'
        df = pd.concat([df, df_compare], ignore_index=True)

    return df


def query_product_stats(
    start_date: date,
    end_date: date,
    platform: str = 'All',
    compare_start: date = None,
    compare_end: date = None
) -> pd.DataFrame:
    conn = init_database()

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

    df = conn.execute(query, [start_date, end_date]).fetchdf()

    if compare_start and compare_end:
        df_compare = conn.execute(query, [compare_start, compare_end]).fetchdf()
        df_compare['period_type'] = 'previous'
        df = pd.concat([df, df_compare], ignore_index=True)

    return df


def query_summary_metrics(
    start_date: date,
    end_date: date,
    platform: str = 'All'
) -> dict:
    conn = init_database()

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


def query_date_range() -> Tuple[date, date]:
    conn = init_database()
    try:
        result = conn.execute("SELECT MIN(date), MAX(date) FROM orders").fetchone()
        if result[0] and result[1]:
            return result[0], result[1]
    except:
        pass
    return date.today(), date.today()


def get_db_stats() -> dict:
    conn = init_database()
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


def is_database_empty() -> bool:
    """Check if data files exist."""
    files = get_data_files()
    return len(files['tiktok']) == 0 and len(files['shopee']) == 0


def has_data() -> bool:
    """Check if data is actually loaded in the database."""
    try:
        conn = init_database()
        count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        return count > 0
    except:
        return False


def load_multiple_uploaded_files(uploaded_files) -> int:
    data_dir = os.path.join(PROJECT_ROOT, 'data')
    os.makedirs(data_dir, exist_ok=True)

    for uploaded_file in uploaded_files:
        dest_path = os.path.join(data_dir, uploaded_file.name)
        with open(dest_path, 'wb') as f:
            f.write(uploaded_file.getvalue())

    global _files_cache, _conn_cache
    _files_cache = None
    _conn_cache = None
    st.cache_resource.clear()

    return len(uploaded_files)
