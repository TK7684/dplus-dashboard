"""
SQLite database module for DPLUS Dashboard.
Provides fast querying for large datasets.
Supports incremental updates with order_id as unique key.
"""

import sqlite3
import os
import pandas as pd
import streamlit as st
from typing import Optional, Tuple, Set
from datetime import date, datetime
import glob
from contextlib import contextmanager
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    DATA_DIR,
    CLOUD_DATA_DIR,
    TIKTOK_PATTERN,
    SHOPEE_PATTERN,
    BLACKLIST_KEYWORDS
)
from utils.logger import get_logger, log_error, log_info, log_data_load

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'dplus_cache.db')

# Logger instance
_logger = None


def _get_logger():
    """Lazy-load logger to avoid circular imports."""
    global _logger
    if _logger is None:
        _logger = get_logger()
    return _logger


@contextmanager
def get_connection():
    """Get SQLite connection with context manager for proper cleanup."""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30.0)
        conn.row_factory = sqlite3.Row
        yield conn
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        log_error(e, {'operation': 'get_connection'})
        raise
    finally:
        if conn:
            conn.close()


def init_database():
    """Initialize the SQLite database with optimized schema."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Create orders table with composite unique key on (order_id, product_name, platform)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    product_name TEXT,
                    quantity INTEGER DEFAULT 0,
                    subtotal_net REAL DEFAULT 0,
                    order_total_amount REAL DEFAULT 0,
                    created_at TEXT,
                    date TEXT,
                    seller_sku TEXT,
                    order_status TEXT,
                    product_category TEXT,
                    UNIQUE(order_id, product_name, platform)
                )
            ''')

            # Create indexes for fast querying
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_date ON orders(date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_platform ON orders(platform)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_date_platform ON orders(date, platform)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_product ON orders(product_name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_order_id ON orders(order_id)')
            # Additional indexes for performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_subtotal ON orders(subtotal_net)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_order_status ON orders(order_status)')

            # Create metadata table to track loaded files
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS loaded_files (
                    filename TEXT PRIMARY KEY,
                    file_mtime REAL,
                    rows_loaded INTEGER,
                    loaded_at TEXT
                )
            ''')

            # Update query planner statistics
            cursor.execute('ANALYZE')

            conn.commit()
            log_info("Database initialized successfully")
    except Exception as e:
        log_error(e, {'operation': 'init_database'})
        raise


def get_loaded_files() -> Set[str]:
    """Get set of already loaded files."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT filename FROM loaded_files')
            return {row[0] for row in cursor.fetchall()}
    except Exception as e:
        log_error(e, {'operation': 'get_loaded_files'})
        return set()


def mark_file_loaded(filename: str, mtime: float, rows: int, cursor=None):
    """Mark a file as loaded. Use provided cursor if available."""
    try:
        if cursor:
            cursor.execute('''
                INSERT OR REPLACE INTO loaded_files (filename, file_mtime, rows_loaded, loaded_at)
                VALUES (?, ?, ?, ?)
            ''', (filename, mtime, rows, datetime.now().isoformat()))
        else:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO loaded_files (filename, file_mtime, rows_loaded, loaded_at)
                    VALUES (?, ?, ?, ?)
                ''', (filename, mtime, rows, datetime.now().isoformat()))
                conn.commit()
        log_data_load(filename, rows, "loaded")
    except Exception as e:
        log_error(e, {'operation': 'mark_file_loaded', 'filename': filename})


def parse_tiktok_date(date_str: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse TikTok date and return (datetime, date)."""
    if pd.isna(date_str) or date_str == '':
        return None, None
    try:
        dt = pd.to_datetime(date_str, format='%d/%m/%Y %H:%M:%S')
        return dt.isoformat(), dt.strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        try:
            dt = pd.to_datetime(date_str, dayfirst=True)
            return dt.isoformat(), dt.strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            return None, None


def parse_shopee_date(date_str: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse Shopee date and return (datetime, date)."""
    if pd.isna(date_str) or date_str == '':
        return None, None
    try:
        dt = pd.to_datetime(date_str, format='%Y-%m-%d %H:%M')
        return dt.isoformat(), dt.strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        try:
            dt = pd.to_datetime(date_str)
            return dt.isoformat(), dt.strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            return None, None


def is_blacklisted(product_name: str) -> bool:
    """Check if product is blacklisted."""
    if pd.isna(product_name):
        return False
    product_lower = str(product_name).lower()
    return any(kw.lower() in product_lower for kw in BLACKLIST_KEYWORDS)


def load_tiktok_to_db(filepath: str, cursor) -> int:
    """Load a TikTok CSV file into database using batch inserts. Supports gzip compression."""
    # Check if file is gzip compressed
    is_gzipped = filepath.endswith('.gz')

    read_csv_kwargs = {'low_memory': False}
    if is_gzipped:
        read_csv_kwargs['compression'] = 'gzip'

    try:
        df = pd.read_csv(filepath, encoding='utf-8', **read_csv_kwargs)
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(filepath, encoding='utf-8-sig', **read_csv_kwargs)
        except UnicodeDecodeError:
            df = pd.read_csv(filepath, encoding='latin-1', **read_csv_kwargs)

    df.columns = df.columns.str.strip()

    # Filter blacklisted products
    product_col = 'Product Name'
    if product_col not in df.columns:
        return 0

    # Fast blacklist filter using vectorized operations
    product_lower = df[product_col].fillna('').str.lower()
    mask = ~product_lower.apply(lambda x: any(kw.lower() in x for kw in BLACKLIST_KEYWORDS))
    df = df[mask]

    # Parse dates - Bangkok timezone (data is already in BKK time)
    df['created_at_dt'] = pd.to_datetime(df['Created Time'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
    if df['created_at_dt'].isna().all():
        df['created_at_dt'] = pd.to_datetime(df['Created Time'], dayfirst=True, errors='coerce')

    df = df[df['created_at_dt'].notna()]
    if df.empty:
        return 0

    df['created_at'] = df['created_at_dt'].dt.strftime('%Y-%m-%dT%H:%M:%S')
    df['date'] = df['created_at_dt'].dt.strftime('%Y-%m-%d')

    # Vectorized data preparation (much faster than iterrows)
    df['order_id'] = df['Order ID'].astype(str).str.strip()
    df['product_name'] = df['Product Name'].astype(str).str.strip().str[:500]
    df['quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(0).astype(int)
    df['subtotal_net'] = pd.to_numeric(df['SKU Subtotal After Discount'], errors='coerce').fillna(0)
    df['order_total_amount'] = pd.to_numeric(df['Order Amount'], errors='coerce').fillna(0)
    df['seller_sku'] = df.get('Seller SKU', '').astype(str).str.strip()
    df['order_status'] = df.get('Order Status', '').astype(str).str.strip()
    df['product_category'] = df.get('Product Category', '').astype(str).str.strip()

    # Prepare batch data using list comprehension (faster)
    batch_data = list(zip(
        df['order_id'],
        ['TikTok'] * len(df),
        df['product_name'],
        df['quantity'],
        df['subtotal_net'],
        df['order_total_amount'],
        df['created_at'],
        df['date'],
        df['seller_sku'],
        df['order_status'],
        df['product_category']
    ))

    # Batch insert
    if batch_data:
        cursor.executemany('''
            INSERT OR REPLACE INTO orders
            (order_id, platform, product_name, quantity, subtotal_net,
             order_total_amount, created_at, date, seller_sku, order_status, product_category)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', batch_data)

    return len(batch_data)


def load_shopee_to_db(filepath: str, cursor) -> int:
    """Load a Shopee Excel file into database using batch inserts."""
    df = pd.read_excel(filepath)

    # Filter blacklisted products
    product_col = 'ชื่อสินค้า'
    if product_col not in df.columns:
        return 0

    # Fast blacklist filter
    product_lower = df[product_col].fillna('').str.lower()
    mask = ~product_lower.apply(lambda x: any(kw.lower() in x for kw in BLACKLIST_KEYWORDS))
    df = df[mask]

    # Parse dates
    df['created_at_dt'] = pd.to_datetime(df['วันที่ทำการสั่งซื้อ'], errors='coerce')
    if df['created_at_dt'].isna().all():
        df['created_at_dt'] = pd.to_datetime(df['วันที่ทำการสั่งซื้อ'], dayfirst=True, errors='coerce')

    df = df[df['created_at_dt'].notna()]
    if df.empty:
        return 0

    df['created_at'] = df['created_at_dt'].dt.strftime('%Y-%m-%dT%H:%M:%S')
    df['date'] = df['created_at_dt'].dt.strftime('%Y-%m-%d')

    # Vectorized data preparation
    df['order_id'] = df['หมายเลขคำสั่งซื้อ'].astype(str).str.strip()
    df['product_name'] = df['ชื่อสินค้า'].astype(str).str.strip().str[:500]
    df['quantity'] = pd.to_numeric(df['จำนวน'], errors='coerce').fillna(0).astype(int)
    df['subtotal_net'] = pd.to_numeric(df['ราคาขายสุทธิ'], errors='coerce').fillna(0)
    df['order_total_amount'] = pd.to_numeric(df['จำนวนเงินทั้งหมด'], errors='coerce').fillna(0)
    df['seller_sku'] = df.get('เลขอ้างอิง SKU (SKU Reference No.)', '').astype(str).str.strip()
    df['order_status'] = df.get('สถานะการสั่งซื้อ', '').astype(str).str.strip()

    # Prepare batch data using list comprehension
    batch_data = list(zip(
        df['order_id'],
        ['Shopee'] * len(df),
        df['product_name'],
        df['quantity'],
        df['subtotal_net'],
        df['order_total_amount'],
        df['created_at'],
        df['date'],
        df['seller_sku'],
        df['order_status']
    ))

    # Batch insert
    if batch_data:
        cursor.executemany('''
            INSERT OR REPLACE INTO orders
            (order_id, platform, product_name, quantity, subtotal_net,
             order_total_amount, created_at, date, seller_sku, order_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', batch_data)

    return len(batch_data)


@st.cache_resource
def build_database(show_progress=True) -> bool:
    """Build the SQLite database from source files."""
    init_database()

    with get_connection() as conn:
        cursor = conn.cursor()

        # Speed optimizations for bulk insert
        cursor.execute("PRAGMA journal_mode = OFF")
        cursor.execute("PRAGMA synchronous = OFF")
        cursor.execute("PRAGMA cache_size = -64000")  # 64MB cache

        # Get already loaded files
        loaded_files = get_loaded_files()

        # Get all files from both local and cloud directories
        tiktok_files = sorted(glob.glob(os.path.join(DATA_DIR, TIKTOK_PATTERN)))
        shopee_files = sorted(glob.glob(os.path.join(DATA_DIR, SHOPEE_PATTERN)))

        # Also check for gzip-compressed TikTok files
        tiktok_files.extend(sorted(glob.glob(os.path.join(DATA_DIR, '*.csv.gz'))))

        # Also check cloud data directory
        if os.path.exists(CLOUD_DATA_DIR):
            tiktok_files.extend(sorted(glob.glob(os.path.join(CLOUD_DATA_DIR, TIKTOK_PATTERN))))
            shopee_files.extend(sorted(glob.glob(os.path.join(CLOUD_DATA_DIR, SHOPEE_PATTERN))))
            # Also check for any xlsx/csv files in cloud dir
            tiktok_files.extend(sorted(glob.glob(os.path.join(CLOUD_DATA_DIR, '*.csv'))))
            tiktok_files.extend(sorted(glob.glob(os.path.join(CLOUD_DATA_DIR, '*.csv.gz'))))
            shopee_files.extend(sorted(glob.glob(os.path.join(CLOUD_DATA_DIR, '*.xlsx'))))

        # Filter to only new/modified files
        new_tiktok = []
        new_shopee = []

        for filepath in tiktok_files:
            filename = os.path.basename(filepath)
            if filename not in loaded_files:
                new_tiktok.append(filepath)

        for filepath in shopee_files:
            filename = os.path.basename(filepath)
            if filename not in loaded_files:
                new_shopee.append(filepath)

        total_files = len(new_tiktok) + len(new_shopee)

        if total_files == 0:
            return True

        if show_progress:
            progress = st.progress(0, text="Loading new data...")
            status = st.empty()

        processed = 0
        total_rows = 0

        # Load new TikTok files
        for filepath in new_tiktok:
            filename = os.path.basename(filepath)
            if show_progress:
                status.text(f"Loading TikTok: {filename}")
            rows = load_tiktok_to_db(filepath, cursor)
            mark_file_loaded(filename, os.path.getmtime(filepath), rows, cursor)
            total_rows += rows
            processed += 1
            if show_progress:
                progress.progress(processed / total_files)

        # Load new Shopee files
        for filepath in new_shopee:
            filename = os.path.basename(filepath)
            if show_progress:
                status.text(f"Loading Shopee: {filename}")
            rows = load_shopee_to_db(filepath, cursor)
            mark_file_loaded(filename, os.path.getmtime(filepath), rows, cursor)
            total_rows += rows
            processed += 1
            if show_progress:
                progress.progress(processed / total_files)

        conn.commit()

        if show_progress:
            progress.empty()
            status.empty()

        if total_rows > 0:
            print(f"[Database] Loaded {total_rows:,} new records from {total_files} files")

        return True


def refresh_database():
    """Refresh database by checking for new/modified files."""
    init_database()

    with get_connection() as conn:
        cursor = conn.cursor()

        # Get all files (including gzip-compressed)
        tiktok_files = sorted(glob.glob(os.path.join(DATA_DIR, TIKTOK_PATTERN)))
        tiktok_files.extend(sorted(glob.glob(os.path.join(DATA_DIR, '*.csv.gz'))))
        shopee_files = sorted(glob.glob(os.path.join(DATA_DIR, SHOPEE_PATTERN)))

        loaded_files = get_loaded_files()

        new_files = []
        for filepath in tiktok_files + shopee_files:
            filename = os.path.basename(filepath)
            if filename not in loaded_files:
                new_files.append(filepath)

        if not new_files:
            return 0

        total_rows = 0
        for filepath in new_files:
            filename = os.path.basename(filepath)
            print(f"[Database] Loading new file: {filename}")

            if filepath.endswith('.csv') or filepath.endswith('.csv.gz'):
                rows = load_tiktok_to_db(filepath, cursor)
            else:
                rows = load_shopee_to_db(filepath, cursor)

            mark_file_loaded(filename, os.path.getmtime(filepath), rows, cursor)
            total_rows += rows

        conn.commit()

        if total_rows > 0:
            print(f"[Database] Refreshed: {total_rows:,} new records from {len(new_files)} files")
            # Clear Streamlit cache
            st.cache_resource.clear()

        return total_rows


def get_new_files_count() -> int:
    """Get count of new files not yet loaded."""
    tiktok_files = sorted(glob.glob(os.path.join(DATA_DIR, TIKTOK_PATTERN)))
    tiktok_files.extend(sorted(glob.glob(os.path.join(DATA_DIR, '*.csv.gz'))))
    shopee_files = sorted(glob.glob(os.path.join(DATA_DIR, SHOPEE_PATTERN)))

    loaded_files = get_loaded_files()

    new_count = 0
    for filepath in tiktok_files + shopee_files:
        filename = os.path.basename(filepath)
        if filename not in loaded_files:
            new_count += 1

    return new_count


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
    """
    Query revenue data aggregated by time period.
    Optionally includes comparison period data.
    """
    # Validate inputs
    if start_date > end_date:
        log_error(ValueError("start_date > end_date"), {'start': str(start_date), 'end': str(end_date)})
        return pd.DataFrame()

    # SQLite date format for grouping
    if granularity == 'D':
        group_expr = 'date'
    elif granularity == 'W':
        group_expr = "strftime('%Y-W%W', date)"
    elif granularity == 'M':
        group_expr = "strftime('%Y-%m', date)"
    else:  # Q
        group_expr = "strftime('%Y', date) || '-Q' || ((CAST(strftime('%m', date) AS INTEGER) - 1) / 3 + 1)"

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

    try:
        with get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=[start_date.isoformat(), end_date.isoformat()])

            # Add comparison period if provided
            if compare_start and compare_end:
                df_compare = pd.read_sql_query(query, conn, params=[compare_start.isoformat(), compare_end.isoformat()])
                df_compare['period_type'] = 'previous'
                df = pd.concat([df, df_compare], ignore_index=True)

            return df
    except Exception as e:
        log_error(e, {'operation': 'query_revenue_by_period', 'start': str(start_date), 'end': str(end_date)})
        return pd.DataFrame()


def query_aov_by_period(
    start_date: date,
    end_date: date,
    granularity: str = 'D',
    platform: str = 'All',
    compare_start: date = None,
    compare_end: date = None
) -> pd.DataFrame:
    """Query AOV data by period."""
    if start_date > end_date:
        return pd.DataFrame()

    if granularity == 'D':
        group_expr = 'date'
    elif granularity == 'W':
        group_expr = "strftime('%Y-W%W', date)"
    elif granularity == 'M':
        group_expr = "strftime('%Y-%m', date)"
    else:
        group_expr = "strftime('%Y', date) || '-Q' || ((CAST(strftime('%m', date) AS INTEGER) - 1) / 3 + 1)"

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

    try:
        with get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=[start_date.isoformat(), end_date.isoformat()])

            if compare_start and compare_end:
                df_compare = pd.read_sql_query(query, conn, params=[compare_start.isoformat(), compare_end.isoformat()])
                df_compare['period_type'] = 'previous'
                df = pd.concat([df, df_compare], ignore_index=True)

            return df
    except Exception as e:
        log_error(e, {'operation': 'query_aov_by_period'})
        return pd.DataFrame()


def query_product_stats(
    start_date: date,
    end_date: date,
    platform: str = 'All',
    compare_start: date = None,
    compare_end: date = None
) -> pd.DataFrame:
    """Query product statistics."""
    if start_date > end_date:
        return pd.DataFrame()

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

    try:
        with get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=[start_date.isoformat(), end_date.isoformat()])

            if compare_start and compare_end:
                df_compare = pd.read_sql_query(query, conn, params=[compare_start.isoformat(), compare_end.isoformat()])
                df_compare['period_type'] = 'previous'
                df = pd.concat([df, df_compare], ignore_index=True)

            return df
    except Exception as e:
        log_error(e, {'operation': 'query_product_stats'})
        return pd.DataFrame()


def query_summary_metrics(
    start_date: date,
    end_date: date,
    platform: str = 'All'
) -> dict:
    """Query summary metrics for a period."""
    default_metrics = {'total_orders': 0, 'total_revenue': 0, 'total_quantity': 0, 'aov': 0, 'unique_products': 0}

    if start_date > end_date:
        return default_metrics

    platform_filter = "" if platform == 'All' else f"AND platform = '{platform}'"

    query = f'''
        SELECT
            COUNT(DISTINCT order_id) as total_orders,
            SUM(subtotal_net) as total_revenue,
            SUM(quantity) as total_quantity,
            SUM(subtotal_net) * 1.0 / COUNT(DISTINCT order_id) as aov,
            COUNT(DISTINCT product_name) as unique_products
        FROM orders
        WHERE date >= ? AND date <= ? {platform_filter}
    '''

    try:
        with get_connection() as conn:
            result = pd.read_sql_query(query, conn, params=[start_date.isoformat(), end_date.isoformat()])

            if result.empty:
                return default_metrics

            return result.iloc[0].to_dict()
    except Exception as e:
        log_error(e, {'operation': 'query_summary_metrics'})
        return default_metrics


def query_date_range() -> Tuple[date, date]:
    """Get the min and max dates in the database."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT MIN(date), MAX(date) FROM orders')
            result = cursor.fetchone()

            if result[0] and result[1]:
                return date.fromisoformat(result[0]), date.fromisoformat(result[1])

            return date.today(), date.today()
    except Exception as e:
        log_error(e, {'operation': 'query_date_range'})
        return date.today(), date.today()


def get_db_stats() -> dict:
    """Get database statistics."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('SELECT COUNT(*) FROM orders')
            total_rows = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(DISTINCT order_id) FROM orders')
            unique_orders = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(DISTINCT product_name) FROM orders')
            unique_products = cursor.fetchone()[0]

            cursor.execute('SELECT platform, COUNT(*) FROM orders GROUP BY platform')
            by_platform = dict(cursor.fetchall())

            return {
                'total_rows': total_rows,
                'unique_orders': unique_orders,
                'unique_products': unique_products,
                'by_platform': by_platform
            }
    except Exception as e:
        log_error(e, {'operation': 'get_db_stats'})
        return {'total_rows': 0, 'unique_orders': 0, 'unique_products': 0, 'by_platform': {}}


def is_database_empty() -> bool:
    """Check if database has no data."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM orders')
            return cursor.fetchone()[0] == 0
    except Exception:
        return True


def load_uploaded_file(uploaded_file) -> int:
    """Load an uploaded file (from Streamlit file uploader) into database."""
    init_database()

    filename = uploaded_file.name.lower()
    total_rows = 0

    with get_connection() as conn:
        cursor = conn.cursor()

        # Save to temp file and process
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name

        try:
            if filename.endswith('.csv') or filename.endswith('.csv.gz'):
                # Check if it's a TikTok file (has Thai characters in pattern)
                if 'คำสั่งซื้อ' in uploaded_file.name or 'tiktok' in filename:
                    total_rows = load_tiktok_to_db(tmp_path, cursor)
            elif filename.endswith('.xlsx'):
                # Check if it's a Shopee file
                if uploaded_file.name.startswith('Order.all.'):
                    total_rows = load_shopee_to_db(tmp_path, cursor)

            conn.commit()
        finally:
            os.unlink(tmp_path)

    return total_rows


def load_multiple_uploaded_files(uploaded_files) -> int:
    """Load multiple uploaded files into database."""
    init_database()
    total_rows = 0

    with get_connection() as conn:
        cursor = conn.cursor()

        for uploaded_file in uploaded_files:
            filename = uploaded_file.name.lower()

            # Save to temp file and process
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name

            try:
                if filename.endswith('.csv') or filename.endswith('.csv.gz'):
                    rows = load_tiktok_to_db(tmp_path, cursor)
                elif filename.endswith('.xlsx'):
                    rows = load_shopee_to_db(tmp_path, cursor)
                else:
                    rows = 0

                total_rows += rows
            finally:
                os.unlink(tmp_path)

        conn.commit()

    return total_rows
