"""
DuckDB database module for DPLUS Dashboard.
Uses persistent database file for instant startup after first load.
"""

import os
import glob
import duckdb
import pandas as pd
import streamlit as st
from typing import Optional, Tuple, Dict
from datetime import date

# Configuration
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_ROOT, 'dplus.duckdb')

# Data directories to check
DATA_DIRS = [
    os.path.join(PROJECT_ROOT, 'Original files'),
    os.path.join(PROJECT_ROOT, 'data'),
]

# Blacklist keywords - ONLY these (case-insensitive)
BLACKLIST_KEYWORDS = ['apple', 'iphone', 'ipad']

# Order statuses to EXCLUDE from revenue calculations (ALL platforms)
# This whitelist approach includes all active orders except cancelled/unpaid
# TikTok:  เสร็จสมบูรณ์ = Completed, จัดส่งแล้ว = Shipped, ที่จะจัดส่ง = To be shipped
# Shopee:  สำเร็จแล้ว = Succeeded, จัดส่งสำเร็จแล้ว = Delivered Successfully
# Excludes: ยกเลิกแล้ว = Cancelled, ค้างชำระ = Unpaid
EXCLUDED_STATUSES = ['ยกเลิกแล้ว', 'ค้างชำระ']

# Keep legacy alias for backward compatibility (deprecated)
INCLUDED_STATUSES = EXCLUDED_STATUSES
TIKTOK_INCLUDED_STATUSES = EXCLUDED_STATUSES

_conn = None

# =============================================================================
# TIKTOK COLUMN MAPPING
# Original fields -> Standardized schema
# =============================================================================
TIKTOK_COLUMN_MAP = {
    'Order ID': 'order_id',
    'Order Status': 'order_status',
    'Order Substatus': 'order_substatus',
    'Cancelation/Return Type': 'cancel_return_type',
    'Normal or Pre-order': 'order_type',
    'SKU ID': 'sku_id',
    'Seller SKU': 'seller_sku',
    'Product Name': 'product_name',
    'Variation': 'variation',
    'Quantity': 'quantity',
    'Sku Quantity of return': 'return_quantity',
    'SKU Unit Original Price': 'unit_original_price',
    'SKU Subtotal Before Discount': 'subtotal_gross',
    'SKU Platform Discount': 'discount_platform',
    'SKU Seller Discount': 'discount_seller',
    'SKU Subtotal After Discount': 'subtotal_net',
    'Shipping Fee After Discount': 'shipping_fee_net',
    'Original Shipping Fee': 'shipping_fee_original',
    'Shipping Fee Seller Discount': 'shipping_fee_discount_seller',
    'Shipping Fee Platform Discount': 'shipping_fee_discount_platform',
    'Payment platform discount': 'payment_platform_discount',
    'Taxes': 'taxes',
    'Small Order Fee': 'small_order_fee',
    'Order Amount': 'order_total_amount',
    'Order Refund Amount': 'refund_amount',
    'Created Time': 'created_at',
    'Paid Time': 'paid_at',
    'RTS Time': 'rts_at',
    'Shipped Time': 'shipped_at',
    'Delivered Time': 'delivered_at',
    'Cancelled Time': 'cancelled_at',
    'Cancel By': 'cancelled_by',
    'Cancel Reason': 'cancel_reason',
    'Fulfillment Type': 'fulfillment_type',
    'Warehouse Name': 'warehouse_name',
    'Tracking ID': 'tracking_id',
    'Delivery Option': 'delivery_option',
    'Shipping Provider Name': 'shipping_provider',
    'Buyer Message': 'buyer_message',
    'Buyer Username': 'buyer_username',
    'Recipient': 'recipient_name',
    'Phone #': 'phone_number',
    'Zipcode': 'zipcode',
    'Country': 'country',
    'Province': 'province',
    'District': 'district',
    'Detail Address': 'address_detail',
    'Additional address information': 'address_additional',
    'Payment Method': 'payment_method',
    'Weight(kg)': 'weight_kg',
    'Product Category': 'category',
    'Package ID': 'package_id',
    'Seller Note': 'seller_note',
    'Checked Status': 'checked_status',
    'Checked Marked by': 'checked_marked_by',
}

# =============================================================================
# SHOPEE COLUMN MAPPING
# Original Thai fields -> Standardized schema
# =============================================================================
SHOPEE_COLUMN_MAP = {
    'หมายเลขคำสั่งซื้อ': 'order_id',
    'สถานะการสั่งซื้อ': 'order_status',
    'Hot Listing': 'hot_listing',
    'เหตุผลในการยกเลิกคำสั่งซื้อ': 'cancel_reason',
    'สถานะการคืนเงินหรือคืนสินค้า': 'return_refund_status',
    'ชื่อผู้ใช้ (ผู้ซื้อ)': 'buyer_username',
    'วันที่ทำการสั่งซื้อ': 'created_at',
    'เวลาการชำระสินค้า': 'paid_at',
    'ช่องทางการชำระเงิน': 'payment_method',
    'ช่องทางการชำระเงิน (รายละเอียด)': 'payment_method_detail',
    'แผนการผ่อนชำระ': 'installment_plan',
    'ค่าธรรมเนียม (%)': 'fee_percentage',
    'ตัวเลือกการจัดส่ง': 'delivery_option',
    'วิธีการจัดส่ง': 'shipping_provider',
    '*หมายเลขติดตามพัสดุ': 'tracking_id',
    'วันที่คาดว่าจะทำการจัดส่งสินค้า': 'estimated_ship_date',
    'เวลาส่งสินค้า': 'shipped_at',
    'เลขอ้างอิง Parent SKU': 'parent_sku_ref',
    'ชื่อสินค้า': 'product_name',
    'เลขอ้างอิง SKU (SKU Reference No.)': 'seller_sku',
    'ชื่อตัวเลือก': 'variation',
    'ราคาตั้งต้น': 'unit_original_price',
    'ราคาขาย': 'unit_deal_price',
    'จำนวน': 'quantity',
    'จำนวนที่ส่งคืน': 'return_quantity',
    'ราคาขายสุทธิ': 'subtotal_net',
    'ส่วนลดจาก Shopee': 'discount_platform',
    'โค้ดส่วนลดชำระโดยผู้ขาย': 'discount_seller',
    'โค้ด Coins Cashback ชำระโดยผู้ขาย': 'seller_coin_cashback',
    'โค้ดส่วนลดชำระโดย Shopee (เช่น โค้ดจากโปรแกรม ร้านโค้ดคุ้ม, โค้ดส่วนลด Shopee, โค้ดส่วนลด Shopee Mall)': 'shopee_voucher_rebate',
    'โค้ดส่วนลด': 'voucher_code',
    'เข้าร่วมแคมเปญ bundle deal หรือไม่': 'is_bundle_deal',
    'ส่วนลด bundle deal ชำระโดยผู้ขาย': 'bundle_discount_seller',
    'ส่วนลด bundle deal ชำระโดย Shopee': 'bundle_discount_platform',
    'ส่วนลดจากการใช้เหรียญ': 'coin_discount',
    'โปรโมชั่นช่องทางชำระเงินทั้งหมด': 'payment_promotion_discount',
    'ส่วนลดเครื่องเก่าแลกใหม่': 'trade_in_discount',
    'โบนัสส่วนลดเครื่องเก่าแลกใหม่': 'trade_in_bonus',
    'ค่าคอมมิชชั่น': 'commission_fee',
    'Transaction Fee': 'transaction_fee',
    'ราคาสินค้าที่ชำระโดยผู้ซื้อ (THB)': 'subtotal_gross',
    'ค่าจัดส่งที่ชำระโดยผู้ซื้อ': 'shipping_fee_net',
    'ค่าจัดส่งที่ Shopee ออกให้โดยประมาณ': 'estimated_shipping_fee',
    'ค่าจัดส่งสินค้าคืน': 'return_shipping_fee',
    'ค่าบริการ': 'service_fee',
    'จำนวนเงินทั้งหมด': 'order_total_amount',
    'ค่าจัดส่งโดยประมาณ': 'shipping_fee_original',
    'โบนัส': 'trade_in_seller_bonus',
}

# Numeric columns that should be stored as DOUBLE in the database
NUMERIC_COLUMNS = {
    'subtotal_net', 'order_total_amount', 'subtotal_gross', 'unit_original_price',
    'unit_deal_price', 'shipping_fee_net', 'shipping_fee_original', 'discount_platform',
    'discount_seller', 'refund_amount', 'taxes', 'weight_kg', 'bundle_discount_platform',
    'bundle_discount_seller', 'shipping_fee_discount_platform', 'shipping_fee_discount_seller',
    'payment_platform_discount', 'payment_promotion_discount', 'return_shipping_fee',
    'estimated_shipping_fee', 'service_fee', 'transaction_fee', 'commission_fee',
    'coin_discount', 'total_settlement_amount', 'trade_in_discount', 'trade_in_bonus',
    'trade_in_seller_bonus', 'seller_coin_cashback', 'shopee_voucher_rebate', 'fee_percentage',
    'small_order_fee'
}

# All columns in the standardized schema (sorted alphabetically)
ALL_SCHEMA_COLUMNS = sorted([
    'address_additional', 'address_detail', 'bundle_discount_platform',
    'bundle_discount_seller', 'buyer_message', 'buyer_username', 'cancel_reason',
    'cancel_return_type', 'cancelled_at', 'cancelled_by', 'category',
    'checked_marked_by', 'checked_status', 'coin_discount', 'commission_fee',
    'completed_at', 'country', 'created_at', 'date', 'delivered_at',
    'delivery_option', 'discount_platform', 'discount_seller', 'district',
    'estimated_ship_date', 'estimated_shipping_fee', 'fee_percentage',
    'fulfillment_type', 'hot_listing', 'installment_plan', 'is_bundle_deal',
    'order_id', 'order_status', 'order_substatus', 'order_total_amount',
    'order_type', 'package_id', 'paid_at', 'parent_sku_ref', 'payment_method',
    'payment_method_detail', 'payment_platform_discount', 'payment_promotion_discount',
    'phone_number', 'platform', 'product_name', 'province', 'quantity',
    'recipient_name', 'refund_amount', 'return_quantity', 'return_refund_status',
    'return_shipping_fee', 'rts_at', 'seller_coin_cashback', 'seller_note',
    'seller_sku', 'service_fee', 'shipped_at', 'shipping_fee_discount_platform',
    'shipping_fee_discount_seller', 'shipping_fee_net', 'shipping_fee_original',
    'shipping_provider', 'shopee_voucher_rebate', 'sku_id', 'small_order_fee',
    'subtotal_gross', 'subtotal_net', 'taxes', 'total_settlement_amount',
    'tracking_id', 'trade_in_bonus', 'trade_in_discount', 'trade_in_seller_bonus',
    'transaction_fee', 'unit_deal_price', 'unit_original_price', 'variation',
    'voucher_code', 'warehouse_name', 'weight_kg', 'zipcode'
])


def get_data_files() -> dict:
    """Get all data files organized by type."""
    tiktok_files = []
    shopee_files = []

    for data_dir in DATA_DIRS:
        if os.path.exists(data_dir):
            tiktok_files.extend(glob.glob(os.path.join(data_dir, '*.csv')))
            tiktok_files.extend(glob.glob(os.path.join(data_dir, '*.csv.gz')))
            shopee_files.extend(glob.glob(os.path.join(data_dir, '*.xlsx')))

    return {'tiktok': tiktok_files, 'shopee': shopee_files}


def is_blacklisted(product_name: str) -> bool:
    """Check if product should be excluded (only apple, iphone, ipad)."""
    if not product_name or pd.isna(product_name):
        return False
    product_lower = str(product_name).lower()
    return any(kw in product_lower for kw in BLACKLIST_KEYWORDS)


def get_file_hash() -> str:
    """Get a hash of all data files to detect changes."""
    files = get_data_files()
    all_files = sorted(files['tiktok'] + files['shopee'])
    hashes = []
    for f in all_files:
        try:
            mtime = os.path.getmtime(f)
            size = os.path.getsize(f)
            hashes.append(f"{f}:{mtime}:{size}")
        except:
            pass
    return str(hash(tuple(hashes)))


@st.cache_resource
def get_connection():
    """Get or create DuckDB connection."""
    global _conn
    if _conn is not None:
        return _conn

    conn = duckdb.connect(DB_PATH, read_only=False)
    conn.execute("SET threads=4")
    conn.execute("SET memory_limit='2GB'")
    _conn = conn
    return conn


def init_database():
    """Initialize database schema with comprehensive fields."""
    conn = get_connection()

    # Drop existing table to recreate with new schema
    conn.execute("DROP TABLE IF EXISTS orders")

    # Create orders table with proper types
    column_definitions = []
    for col in ALL_SCHEMA_COLUMNS:
        if col == 'date':
            column_definitions.append(f'{col} DATE')
        elif col == 'quantity':
            column_definitions.append(f'{col} INTEGER')
        elif col in NUMERIC_COLUMNS:
            column_definitions.append(f'{col} DOUBLE')
        else:
            column_definitions.append(f'{col} VARCHAR')

    columns_sql = ', '.join(column_definitions)

    print(f"[DEBUG] Creating orders table with schema:")
    for col_def in column_definitions:
        if 'subtotal_net' in col_def or 'order_total_amount' in col_def:
            print(f"  {col_def}")

    conn.execute(f'''
        CREATE TABLE orders (
            {columns_sql}
        )
    ''')

    # Create indexes for common queries
    conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_platform ON orders(platform)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_order_id ON orders(order_id)")

    # Create metadata table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS metadata (
            key VARCHAR PRIMARY KEY,
            value VARCHAR
        )
    ''')

    return conn


def needs_refresh() -> bool:
    """Check if database needs to be refreshed."""
    conn = init_database()

    # Check if we have any data
    count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    if count == 0:
        return True

    # Check if files have changed
    try:
        stored_hash = conn.execute(
            "SELECT value FROM metadata WHERE key='file_hash'"
        ).fetchone()
        current_hash = get_file_hash()
        if stored_hash is None or stored_hash[0] != current_hash:
            return True
    except:
        return True

    return False


def _parse_tiktok_date(date_str) -> Optional[pd.Timestamp]:
    """Parse TikTok date format: DD/MM/YYYY HH:MM:SS and localize to Bangkok timezone."""
    if pd.isna(date_str) or date_str == '':
        return None
    # Strip whitespace and tab characters
    date_str = str(date_str).strip()
    try:
        dt = pd.to_datetime(date_str, format='%d/%m/%Y %H:%M:%S', errors='coerce')
        if pd.notna(dt):
            # Localize to Bangkok timezone (Thailand has no DST)
            return dt.tz_localize('Asia/Bangkok')
    except:
        try:
            dt = pd.to_datetime(date_str, dayfirst=True, errors='coerce')
            if pd.notna(dt):
                return dt.tz_localize('Asia/Bangkok')
        except:
            pass
    return None


def _parse_shopee_date(date_str) -> Optional[pd.Timestamp]:
    """Parse Shopee date format: YYYY-MM-DD HH:MM and localize to Bangkok timezone."""
    if pd.isna(date_str) or date_str == '':
        return None
    try:
        dt = pd.to_datetime(date_str, errors='coerce')
        if pd.notna(dt):
            # Localize to Bangkok timezone (Thailand has no DST)
            return dt.tz_localize('Asia/Bangkok')
    except:
        pass
    return None


def _clean_numeric(value, default=0):
    """Clean and convert numeric values."""
    if pd.isna(value) or value == '':
        return default
    try:
        return float(value)
    except:
        return default


def _clean_string(value, max_len=None):
    """Clean and convert string values."""
    if pd.isna(value):
        return ''
    result = str(value).strip()
    if max_len:
        result = result[:max_len]
    return result


def load_tiktok_files(conn) -> Tuple[int, int]:
    """Load TikTok CSV files into database.
    Returns (rows_loaded, duplicates_skipped)
    """
    files = get_data_files()['tiktok']
    if not files:
        return 0, 0

    all_dfs = []
    total_duplicates = 0

    for filepath in files:
        try:
            # Read CSV
            is_gzipped = filepath.endswith('.gz')
            kwargs = {'low_memory': False}
            if is_gzipped:
                kwargs['compression'] = 'gzip'

            try:
                df = pd.read_csv(filepath, encoding='utf-8', **kwargs)
            except UnicodeDecodeError:
                try:
                    df = pd.read_csv(filepath, encoding='utf-8-sig', **kwargs)
                except:
                    df = pd.read_csv(filepath, encoding='latin-1', **kwargs)

            df.columns = df.columns.str.strip()

            if 'Product Name' not in df.columns or 'Order ID' not in df.columns:
                print(f"Skipping {filepath}: missing required columns")
                continue

            # Filter blacklisted products (only apple, iphone, ipad)
            before_filter = len(df)
            df = df[~df['Product Name'].fillna('').apply(is_blacklisted)]
            if df.empty:
                continue

            # Rename columns according to mapping
            df = df.rename(columns=TIKTOK_COLUMN_MAP)

            # Add platform
            df['platform'] = 'TikTok'

            # Parse created_at date
            df['created_at_dt'] = df['created_at'].apply(_parse_tiktok_date)
            df = df[df['created_at_dt'].notna()]
            if df.empty:
                continue

            df['created_at'] = df['created_at_dt']
            df['date'] = df['created_at_dt'].dt.date

            # Remove empty order_ids
            df['order_id'] = df['order_id'].astype(str).str.strip()
            df = df[df['order_id'] != '']
            if df.empty:
                continue

            all_dfs.append(df)

        except Exception as e:
            print(f"Error loading {filepath}: {e}")

    if not all_dfs:
        return 0, 0

    # Combine all TikTok data
    combined_df = pd.concat(all_dfs, ignore_index=True)

    # CRITICAL: Deduplicate by order_id + platform (keep first occurrence)
    before_dedup = len(combined_df)
    combined_df = combined_df.drop_duplicates(subset=['order_id', 'platform'], keep='first')
    total_duplicates = before_dedup - len(combined_df)

    # Select only columns that exist in our schema
    available_cols = [col for col in ALL_SCHEMA_COLUMNS if col in combined_df.columns]

    # Fill missing columns with empty/default values
    for col in ALL_SCHEMA_COLUMNS:
        if col not in combined_df.columns:
            if col == 'quantity':
                combined_df[col] = 0
            else:
                combined_df[col] = ''

    final_df = combined_df[ALL_SCHEMA_COLUMNS].copy()

    # Clean up numeric columns - use the same NUMERIC_COLUMNS set
    for col in NUMERIC_COLUMNS:
        if col in final_df.columns:
            final_df[col] = pd.to_numeric(final_df[col], errors='coerce').fillna(0)

    # Clean string columns - exclude numeric columns
    for col in final_df.columns:
        if col not in ['date', 'created_at', 'quantity'] and col not in NUMERIC_COLUMNS and final_df[col].dtype == 'object':
            final_df[col] = final_df[col].fillna('').astype(str).str.strip()

    # Insert into database
    conn.execute("INSERT INTO orders SELECT * FROM final_df")

    return len(final_df), total_duplicates


def load_shopee_files(conn) -> Tuple[int, int]:
    """Load Shopee Excel files into database.
    Returns (rows_loaded, duplicates_skipped)
    """
    files = get_data_files()['shopee']
    if not files:
        return 0, 0

    all_dfs = []
    total_duplicates = 0

    for filepath in files:
        try:
            df = pd.read_excel(filepath)

            # Check for required columns
            required_cols = ['หมายเลขคำสั่งซื้อ', 'ชื่อสินค้า']
            if not all(col in df.columns for col in required_cols):
                print(f"Skipping {filepath}: missing required columns")
                continue

            # Filter blacklisted products (only apple, iphone, ipad)
            df = df[~df['ชื่อสินค้า'].fillna('').apply(is_blacklisted)]
            if df.empty:
                continue

            # Rename columns according to mapping
            df = df.rename(columns=SHOPEE_COLUMN_MAP)

            # Add platform
            df['platform'] = 'Shopee'

            # Parse created_at date
            df['created_at_dt'] = df['created_at'].apply(_parse_shopee_date)
            df = df[df['created_at_dt'].notna()]
            if df.empty:
                continue

            df['created_at'] = df['created_at_dt']
            df['date'] = df['created_at_dt'].dt.date

            # Remove empty order_ids
            df['order_id'] = df['order_id'].astype(str).str.strip()
            df = df[df['order_id'] != '']
            if df.empty:
                continue

            all_dfs.append(df)

        except Exception as e:
            print(f"Error loading {filepath}: {e}")

    if not all_dfs:
        return 0, 0

    # Combine all Shopee data
    combined_df = pd.concat(all_dfs, ignore_index=True)

    # CRITICAL: Deduplicate by order_id + platform (keep first occurrence)
    before_dedup = len(combined_df)
    combined_df = combined_df.drop_duplicates(subset=['order_id', 'platform'], keep='first')
    total_duplicates = before_dedup - len(combined_df)

    # Fill missing columns with empty/default values
    for col in ALL_SCHEMA_COLUMNS:
        if col not in combined_df.columns:
            if col == 'quantity':
                combined_df[col] = 0
            else:
                combined_df[col] = ''

    final_df = combined_df[ALL_SCHEMA_COLUMNS].copy()

    # Clean up numeric columns - use the same NUMERIC_COLUMNS set
    for col in NUMERIC_COLUMNS:
        if col in final_df.columns:
            final_df[col] = pd.to_numeric(final_df[col], errors='coerce').fillna(0)

    # Clean string columns - exclude numeric columns
    for col in final_df.columns:
        if col not in ['date', 'created_at', 'quantity'] and col not in NUMERIC_COLUMNS and final_df[col].dtype == 'object':
            final_df[col] = final_df[col].fillna('').astype(str).str.strip()

    # Insert into database
    conn.execute("INSERT INTO orders SELECT * FROM final_df")

    return len(final_df), total_duplicates


@st.cache_resource
def build_database(show_progress=True) -> bool:
    """Build database if needed. Fast on subsequent loads."""
    conn = init_database()

    if not needs_refresh():
        count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        unique_orders = conn.execute("SELECT COUNT(DISTINCT order_id) FROM orders").fetchone()[0]
        print(f"[DuckDB] Using cached database: {count:,} records, {unique_orders:,} unique orders")
        return True

    # Clear existing data
    conn.execute("DELETE FROM orders")

    print("[DuckDB] Loading data files...")

    # Load data
    tiktok_rows, tiktok_dups = load_tiktok_files(conn)
    shopee_rows, shopee_dups = load_shopee_files(conn)

    # Final deduplication across platforms (should not be needed but safety check)
    # This ensures no duplicate order_ids within the same platform
    total_before = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]

    # Get count of duplicates (same order_id + platform combination)
    dup_check = conn.execute('''
        SELECT COUNT(*) FROM (
            SELECT order_id, platform, COUNT(*) as cnt
            FROM orders
            GROUP BY order_id, platform
            HAVING cnt > 1
        )
    ''').fetchone()[0]

    if dup_check > 0:
        print(f"[DuckDB] WARNING: Found {dup_check} duplicate order_id+platform combinations, removing...")
        # Remove duplicates keeping first occurrence
        conn.execute('''
            DELETE FROM orders
            WHERE ctid NOT IN (
                SELECT MIN(ctid)
                FROM orders
                GROUP BY order_id, platform
            )
        ''')

    # Store file hash
    conn.execute(
        "INSERT OR REPLACE INTO metadata (key, value) VALUES ('file_hash', ?)",
        [get_file_hash()]
    )

    total = tiktok_rows + shopee_rows
    unique_orders = conn.execute("SELECT COUNT(DISTINCT order_id) FROM orders").fetchone()[0]
    print(f"[DuckDB] Loaded: {total:,} records ({unique_orders:,} unique orders)")
    print(f"[DuckDB] TikTok: {tiktok_rows:,} rows ({tiktok_dups:,} duplicates removed)")
    print(f"[DuckDB] Shopee: {shopee_rows:,} rows ({shopee_dups:,} duplicates removed)")

    return True


def refresh_database() -> int:
    """Force refresh database."""
    global _conn
    conn = init_database()
    conn.execute("DELETE FROM orders")
    conn.execute("DELETE FROM metadata WHERE key='file_hash'")
    st.cache_resource.clear()
    _conn = None
    build_database(show_progress=False)
    return conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]


def get_new_files_count() -> int:
    return 0


# =============================================================================
# Helper: build status filter SQL fragment
# Applies to ALL platforms - matches BigQuery reference queries exactly
# =============================================================================
def _build_status_filter() -> str:
    """Return the SQL AND clause for filtering by excluded statuses.
    
    Uses blacklist approach: exclude only cancelled and unpaid orders.
    Includes all active orders (completed, shipped, to be shipped, etc.).
    """
    statuses = "', '".join(EXCLUDED_STATUSES)
    return f"AND order_status NOT IN ('{statuses}')"


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
    conn = get_connection()

    if granularity == 'D':
        group_expr = 'date'
    elif granularity == 'W':
        group_expr = "DATE_TRUNC('week', date)"
    elif granularity == 'M':
        group_expr = "DATE_TRUNC('month', date)"
    else:
        group_expr = "DATE_TRUNC('quarter', date)"

    platform_filter = "" if platform == 'All' else f"AND platform = '{platform}'"
    status_filter = _build_status_filter()

    query = f'''
        SELECT
            {group_expr} as period,
            platform,
            SUM(subtotal_net) as revenue,
            COUNT(DISTINCT order_id) as orders,
            SUM(quantity) as quantity,
            'current' as period_type
        FROM orders
        WHERE date >= ? AND date <= ? {platform_filter} {status_filter}
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
    conn = get_connection()

    if granularity == 'D':
        group_expr = 'date'
    elif granularity == 'W':
        group_expr = "DATE_TRUNC('week', date)"
    elif granularity == 'M':
        group_expr = "DATE_TRUNC('month', date)"
    else:
        group_expr = "DATE_TRUNC('quarter', date)"

    platform_filter = "" if platform == 'All' else f"AND platform = '{platform}'"
    status_filter = _build_status_filter()

    query = f'''
        SELECT
            {group_expr} as period,
            platform,
            SUM(subtotal_net) as revenue,
            COUNT(DISTINCT order_id) as orders,
            SUM(subtotal_net) * 1.0 / COUNT(DISTINCT order_id) as aov,
            'current' as period_type
        FROM orders
        WHERE date >= ? AND date <= ? {platform_filter} {status_filter}
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
    conn = get_connection()

    platform_filter = "" if platform == 'All' else f"AND platform = '{platform}'"
    status_filter = _build_status_filter()

    query = f'''
        SELECT
            product_name,
            platform,
            SUM(subtotal_net) as revenue,
            SUM(quantity) as quantity,
            COUNT(DISTINCT order_id) as orders,
            'current' as period_type
        FROM orders
        WHERE date >= ? AND date <= ? {platform_filter} {status_filter}
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
    conn = get_connection()

    platform_filter = "" if platform == 'All' else f"AND platform = '{platform}'"
    status_filter = _build_status_filter()

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
        WHERE date >= ? AND date <= ? {platform_filter} {status_filter}
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
    conn = get_connection()
    try:
        result = conn.execute("SELECT MIN(date), MAX(date) FROM orders").fetchone()
        if result[0] and result[1]:
            return result[0], result[1]
    except:
        pass
    return date.today(), date.today()


def get_db_stats() -> dict:
    conn = get_connection()
    try:
        total_rows = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        unique_orders = conn.execute("SELECT COUNT(DISTINCT order_id) FROM orders").fetchone()[0]
        unique_products = conn.execute("SELECT COUNT(DISTINCT product_name) FROM orders").fetchone()[0]

        by_platform = {}
        result = conn.execute("SELECT platform, COUNT(*) FROM orders GROUP BY platform").fetchall()
        for row in result:
            by_platform[row[0]] = row[1]

        # Check for duplicates
        dup_count = conn.execute('''
            SELECT COUNT(*) FROM (
                SELECT order_id, platform
                FROM orders
                GROUP BY order_id, platform
                HAVING COUNT(*) > 1
            )
        ''').fetchone()[0]

        return {
            'total_rows': total_rows,
            'unique_orders': unique_orders,
            'unique_products': unique_products,
            'by_platform': by_platform,
            'duplicate_count': dup_count
        }
    except:
        return {'total_rows': 0, 'unique_orders': 0, 'unique_products': 0, 'by_platform': {}, 'duplicate_count': 0}


def is_database_empty() -> bool:
    files = get_data_files()
    return len(files['tiktok']) == 0 and len(files['shopee']) == 0


def has_data() -> bool:
    try:
        conn = get_connection()
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

    # Force refresh
    st.cache_resource.clear()
    global _conn
    _conn = None

    return len(uploaded_files)


# =============================================================================
# Platform Comparison Queries (DOD/WOW/MOM/QOQ)
# =============================================================================

def get_comparison_periods(
    current_start: date,
    current_end: date,
    comparison_type: str
) -> Tuple[date, date]:
    """
    Calculate comparison period based on type.

    Args:
        current_start: Start of current period
        current_end: End of current period
        comparison_type: One of 'DOD', 'WOW', 'MOM', 'QOQ_CONSECUTIVE', 'QOQ_SEQUENTIAL', 'QOQ_YOY'

    Returns:
        Tuple of (comparison_start, comparison_end)
    """
    from dateutil.relativedelta import relativedelta

    period_length = (current_end - current_start).days + 1

    if comparison_type == 'DOD':
        # Day-over-Day: Previous day
        compare_end = current_start - timedelta(days=1)
        compare_start = compare_end

    elif comparison_type == 'WOW':
        # Week-over-Week: Same period previous week
        compare_start = current_start - timedelta(weeks=1)
        compare_end = current_end - timedelta(weeks=1)

    elif comparison_type == 'MOM':
        # Month-over-Month: Same period previous month
        compare_start = current_start - relativedelta(months=1)
        compare_end = current_end - relativedelta(months=1)

    elif comparison_type == 'QOQ_CONSECUTIVE':
        # Consecutive quarters: Q1->Q4(prev year), Q2->Q1, Q3->Q2, Q4->Q3
        current_quarter = (current_start.month - 1) // 3 + 1
        current_year = current_start.year

        if current_quarter == 1:
            # Compare to Q4 of previous year
            compare_quarter = 4
            compare_year = current_year - 1
        else:
            # Compare to previous quarter same year
            compare_quarter = current_quarter - 1
            compare_year = current_year

        # Get first day of comparison quarter
        compare_start = date(compare_year, (compare_quarter - 1) * 3 + 1, 1)
        # Get last day of comparison quarter
        if compare_quarter == 4:
            compare_end = date(compare_year, 12, 31)
        else:
            next_quarter_start = date(compare_year, compare_quarter * 3 + 1, 1)
            compare_end = next_quarter_start - timedelta(days=1)

    elif comparison_type == 'QOQ_SEQUENTIAL':
        # Sequential quarters: Q1->Q2, Q2->Q3, Q3->Q4, Q4->Q1(next year)
        current_quarter = (current_start.month - 1) // 3 + 1
        current_year = current_start.year

        if current_quarter == 4:
            # Compare to Q1 of next year
            compare_quarter = 1
            compare_year = current_year + 1
        else:
            # Compare to next quarter same year
            compare_quarter = current_quarter + 1
            compare_year = current_year

        compare_start = date(compare_year, (compare_quarter - 1) * 3 + 1, 1)
        if compare_quarter == 4:
            compare_end = date(compare_year, 12, 31)
        else:
            next_quarter_start = date(compare_year, compare_quarter * 3 + 1, 1)
            compare_end = next_quarter_start - timedelta(days=1)

    elif comparison_type == 'QOQ_YOY':
        # Same quarter previous year
        compare_start = current_start - relativedelta(years=1)
        compare_end = current_end - relativedelta(years=1)

    else:
        # Default: Previous period of same length
        compare_end = current_start - timedelta(days=1)
        compare_start = compare_end - timedelta(days=period_length - 1)

    return compare_start, compare_end


def query_platform_comparison(
    comparison_type: str,
    current_start: date,
    current_end: date,
    previous_start: date = None,
    previous_end: date = None,
    platform: str = 'All'
) -> pd.DataFrame:
    """
    Query for platform-specific time comparisons.

    Args:
        comparison_type: 'DOD', 'WOW', 'MOM', 'QOQ_CONSECUTIVE', 'QOQ_SEQUENTIAL', 'QOQ_YOY'
        current_start: Start of current period
        current_end: End of current period
        previous_start: Start of comparison period (auto-calculated if None)
        previous_end: End of comparison period (auto-calculated if None)
        platform: 'All', 'TikTok', or 'Shopee'

    Returns:
        DataFrame with columns:
        - platform
        - current_revenue, previous_revenue
        - current_orders, previous_orders
        - current_aov, previous_aov
        - revenue_change, revenue_change_pct
        - order_change, order_change_pct
        - aov_change, aov_change_pct
    """
    conn = get_connection()

    # Calculate comparison periods if not provided
    if previous_start is None or previous_end is None:
        previous_start, previous_end = get_comparison_periods(
            current_start, current_end, comparison_type
        )

    platform_filter_current = "" if platform == 'All' else f"AND platform = ?"
    platform_filter_previous = "" if platform == 'All' else f"AND platform = ?"
    status_filter = _build_status_filter()

    query = f'''
        WITH current_period AS (
            SELECT
                platform,
                SUM(subtotal_net) as revenue,
                COUNT(DISTINCT order_id) as orders,
                CASE WHEN COUNT(DISTINCT order_id) > 0
                     THEN SUM(subtotal_net) * 1.0 / COUNT(DISTINCT order_id)
                     ELSE 0 END as aov
            FROM orders
            WHERE date >= ? AND date <= ? {platform_filter_current} {status_filter}
            GROUP BY platform
        ),
        previous_period AS (
            SELECT
                platform,
                SUM(subtotal_net) as revenue,
                COUNT(DISTINCT order_id) as orders,
                CASE WHEN COUNT(DISTINCT order_id) > 0
                     THEN SUM(subtotal_net) * 1.0 / COUNT(DISTINCT order_id)
                     ELSE 0 END as aov
            FROM orders
            WHERE date >= ? AND date <= ? {platform_filter_previous} {status_filter}
            GROUP BY platform
        )
        SELECT
            COALESCE(c.platform, p.platform) as platform,
            COALESCE(c.revenue, 0) as current_revenue,
            COALESCE(p.revenue, 0) as previous_revenue,
            COALESCE(c.orders, 0) as current_orders,
            COALESCE(p.orders, 0) as previous_orders,
            COALESCE(c.aov, 0) as current_aov,
            COALESCE(p.aov, 0) as previous_aov,
            COALESCE(c.revenue, 0) - COALESCE(p.revenue, 0) as revenue_change,
            CASE WHEN COALESCE(p.revenue, 0) > 0
                 THEN ((COALESCE(c.revenue, 0) - COALESCE(p.revenue, 0)) * 100.0 / p.revenue)
                 ELSE 0 END as revenue_change_pct,
            COALESCE(c.orders, 0) - COALESCE(p.orders, 0) as order_change,
            CASE WHEN COALESCE(p.orders, 0) > 0
                 THEN ((COALESCE(c.orders, 0) - COALESCE(p.orders, 0)) * 100.0 / p.orders)
                 ELSE 0 END as order_change_pct,
            COALESCE(c.aov, 0) - COALESCE(p.aov, 0) as aov_change,
            CASE WHEN COALESCE(p.aov, 0) > 0
                 THEN ((COALESCE(c.aov, 0) - COALESCE(p.aov, 0)) * 100.0 / p.aov)
                 ELSE 0 END as aov_change_pct
        FROM current_period c
        FULL OUTER JOIN previous_period p ON c.platform = p.platform
        ORDER BY platform
    '''

    # Build parameters list
    if platform == 'All':
        params = [current_start, current_end, previous_start, previous_end]
    else:
        params = [current_start, current_end, platform, previous_start, previous_end, platform]

    df = conn.execute(query, params).fetchdf()

    # Add comparison type to result
    df['comparison_type'] = comparison_type

    return df


def query_all_platform_comparisons(
    current_start: date,
    current_end: date,
    platform: str = 'All'
) -> Dict[str, pd.DataFrame]:
    """
    Run all comparison types and return results.

    Args:
        current_start: Start of current period
        current_end: End of current period
        platform: 'All', 'TikTok', or 'Shopee'

    Returns:
        Dictionary with comparison results for each type:
        - 'DOD': Day-over-Day
        - 'WOW': Week-over-Week
        - 'MOM': Month-over-Month
        - 'QOQ_CONSECUTIVE': Consecutive quarters
        - 'QOQ_SEQUENTIAL': Sequential quarters
        - 'QOQ_YOY': Same quarter previous year
    """
    results = {}

    comparison_types = ['DOD', 'WOW', 'MOM', 'QOQ_CONSECUTIVE', 'QOQ_SEQUENTIAL', 'QOQ_YOY']

    for comp_type in comparison_types:
        try:
            results[comp_type] = query_platform_comparison(
                comparison_type=comp_type,
                current_start=current_start,
                current_end=current_end,
                platform=platform
            )
        except Exception as e:
            print(f"Error in {comp_type} comparison: {e}")
            results[comp_type] = pd.DataFrame()

    return results


def query_top3_revenue_days(
    start_date: date,
    end_date: date,
    platform: str = 'All'
) -> pd.DataFrame:
    """Query top 3 highest revenue days (Max tier: PERCENT_RANK >= 0.8)."""
    conn = get_connection()

    platform_filter = "" if platform == 'All' else f"AND platform = '{platform}'"
    status_filter = _build_status_filter()

    query = f'''
        WITH daily_revenue AS (
            SELECT
                date,
                SUM(subtotal_net) as revenue,
                COUNT(DISTINCT order_id) as orders
            FROM orders
            WHERE date >= ? AND date <= ? {platform_filter} {status_filter}
            GROUP BY date
        ),
        ranked AS (
            SELECT *,
                PERCENT_RANK() OVER (ORDER BY revenue ASC) as percentile
            FROM daily_revenue
        )
        SELECT date, revenue, orders
        FROM ranked
        WHERE percentile >= 0.8
        ORDER BY revenue DESC
        LIMIT 3
    '''

    return conn.execute(query, [start_date, end_date]).fetchdf()


def query_bottom3_revenue_days(
    start_date: date,
    end_date: date,
    platform: str = 'All'
) -> pd.DataFrame:
    """Query bottom 3 lowest revenue days (Min tier: PERCENT_RANK <= 0.2)."""
    conn = get_connection()

    platform_filter = "" if platform == 'All' else f"AND platform = '{platform}'"
    status_filter = _build_status_filter()

    query = f'''
        WITH daily_revenue AS (
            SELECT
                date,
                SUM(subtotal_net) as revenue,
                COUNT(DISTINCT order_id) as orders
            FROM orders
            WHERE date >= ? AND date <= ? {platform_filter} {status_filter}
            GROUP BY date
        ),
        ranked AS (
            SELECT *,
                PERCENT_RANK() OVER (ORDER BY revenue ASC) as percentile
            FROM daily_revenue
        )
        SELECT date, revenue, orders
        FROM ranked
        WHERE percentile <= 0.2
        ORDER BY revenue ASC
        LIMIT 3
    '''

    return conn.execute(query, [start_date, end_date]).fetchdf()


def query_top3_aov_days(
    start_date: date,
    end_date: date,
    platform: str = 'All'
) -> pd.DataFrame:
    """Query top 3 highest AOV days (Max tier: PERCENT_RANK >= 0.8)."""
    conn = get_connection()

    platform_filter = "" if platform == 'All' else f"AND platform = '{platform}'"
    status_filter = _build_status_filter()

    query = f'''
        WITH daily_aov AS (
            SELECT
                date,
                SUM(subtotal_net) as revenue,
                COUNT(DISTINCT order_id) as orders,
                CASE WHEN COUNT(DISTINCT order_id) > 0
                     THEN SUM(subtotal_net) * 1.0 / COUNT(DISTINCT order_id)
                     ELSE 0 END as aov
            FROM orders
            WHERE date >= ? AND date <= ? {platform_filter} {status_filter}
            GROUP BY date
            HAVING COUNT(DISTINCT order_id) > 0
        ),
        ranked AS (
            SELECT *,
                PERCENT_RANK() OVER (ORDER BY aov ASC) as percentile
            FROM daily_aov
        )
        SELECT date, revenue, orders, aov
        FROM ranked
        WHERE percentile >= 0.8
        ORDER BY aov DESC
        LIMIT 3
    '''

    return conn.execute(query, [start_date, end_date]).fetchdf()


def query_bottom3_aov_days(
    start_date: date,
    end_date: date,
    platform: str = 'All'
) -> pd.DataFrame:
    """Query bottom 3 lowest AOV days (Min tier: PERCENT_RANK <= 0.2)."""
    conn = get_connection()

    platform_filter = "" if platform == 'All' else f"AND platform = '{platform}'"
    status_filter = _build_status_filter()

    query = f'''
        WITH daily_aov AS (
            SELECT
                date,
                SUM(subtotal_net) as revenue,
                COUNT(DISTINCT order_id) as orders,
                CASE WHEN COUNT(DISTINCT order_id) > 0
                     THEN SUM(subtotal_net) * 1.0 / COUNT(DISTINCT order_id)
                     ELSE 0 END as aov
            FROM orders
            WHERE date >= ? AND date <= ? {platform_filter} {status_filter}
            GROUP BY date
            HAVING COUNT(DISTINCT order_id) > 0
        ),
        ranked AS (
            SELECT *,
                PERCENT_RANK() OVER (ORDER BY aov ASC) as percentile
            FROM daily_aov
        )
        SELECT date, revenue, orders, aov
        FROM ranked
        WHERE percentile <= 0.2
        ORDER BY aov ASC
        LIMIT 3
    '''

    return conn.execute(query, [start_date, end_date]).fetchdf()


def query_top3_order_days(
    start_date: date,
    end_date: date,
    platform: str = 'All'
) -> pd.DataFrame:
    """Query top 3 highest order count days (Max tier: PERCENT_RANK >= 0.8)."""
    conn = get_connection()

    platform_filter = "" if platform == 'All' else f"AND platform = '{platform}'"
    status_filter = _build_status_filter()

    query = f'''
        WITH daily_orders AS (
            SELECT
                date,
                COUNT(DISTINCT order_id) as orders,
                SUM(subtotal_net) as revenue
            FROM orders
            WHERE date >= ? AND date <= ? {platform_filter} {status_filter}
            GROUP BY date
        ),
        ranked AS (
            SELECT *,
                PERCENT_RANK() OVER (ORDER BY orders ASC) as percentile
            FROM daily_orders
        )
        SELECT date, orders, revenue
        FROM ranked
        WHERE percentile >= 0.8
        ORDER BY orders DESC
        LIMIT 3
    '''

    return conn.execute(query, [start_date, end_date]).fetchdf()


def query_bottom3_order_days(
    start_date: date,
    end_date: date,
    platform: str = 'All'
) -> pd.DataFrame:
    """Query bottom 3 lowest order count days (Min tier: PERCENT_RANK <= 0.2)."""
    conn = get_connection()

    platform_filter = "" if platform == 'All' else f"AND platform = '{platform}'"
    status_filter = _build_status_filter()

    query = f'''
        WITH daily_orders AS (
            SELECT
                date,
                COUNT(DISTINCT order_id) as orders,
                SUM(subtotal_net) as revenue
            FROM orders
            WHERE date >= ? AND date <= ? {platform_filter} {status_filter}
            GROUP BY date
        ),
        ranked AS (
            SELECT *,
                PERCENT_RANK() OVER (ORDER BY orders ASC) as percentile
            FROM daily_orders
        )
        SELECT date, orders, revenue
        FROM ranked
        WHERE percentile <= 0.2
        ORDER BY orders ASC
        LIMIT 3
    '''

    return conn.execute(query, [start_date, end_date]).fetchdf()


def query_top3_products(
    start_date: date,
    end_date: date,
    platform: str = 'All'
) -> pd.DataFrame:
    """Query top 3 products by revenue (Max tier: PERCENT_RANK >= 0.8)."""
    conn = get_connection()

    platform_filter = "" if platform == 'All' else f"AND platform = '{platform}'"
    status_filter = _build_status_filter()

    query = f'''
        WITH product_revenue AS (
            SELECT
                product_name,
                SUM(subtotal_net) as revenue,
                SUM(quantity) as quantity,
                COUNT(DISTINCT order_id) as orders
            FROM orders
            WHERE date >= ? AND date <= ? {platform_filter} {status_filter}
            GROUP BY product_name
        ),
        ranked AS (
            SELECT *,
                PERCENT_RANK() OVER (ORDER BY revenue ASC) as percentile
            FROM product_revenue
        )
        SELECT product_name, revenue, quantity, orders
        FROM ranked
        WHERE percentile >= 0.8
        ORDER BY revenue DESC
        LIMIT 3
    '''

    return conn.execute(query, [start_date, end_date]).fetchdf()


def query_top3_products_by_orders(
    start_date: date,
    end_date: date,
    platform: str = 'All'
) -> pd.DataFrame:
    """Query top 3 products by order count (Max tier: PERCENT_RANK >= 0.8)."""
    conn = get_connection()

    platform_filter = "" if platform == 'All' else f"AND platform = '{platform}'"
    status_filter = _build_status_filter()

    query = f'''
        WITH product_orders AS (
            SELECT
                product_name,
                COUNT(DISTINCT order_id) as orders,
                SUM(subtotal_net) as revenue,
                SUM(quantity) as quantity
            FROM orders
            WHERE date >= ? AND date <= ? {platform_filter} {status_filter}
            GROUP BY product_name
        ),
        ranked AS (
            SELECT *,
                PERCENT_RANK() OVER (ORDER BY orders ASC) as percentile
            FROM product_orders
        )
        SELECT product_name, orders, revenue, quantity
        FROM ranked
        WHERE percentile >= 0.8
        ORDER BY orders DESC
        LIMIT 3
    '''

    return conn.execute(query, [start_date, end_date]).fetchdf()


def query_middle3_revenue_days(
    start_date: date,
    end_date: date,
    platform: str = 'All'
) -> pd.DataFrame:
    """Query middle 3 revenue days (Middle tier: 0.2 < PERCENT_RANK < 0.8)."""
    conn = get_connection()

    platform_filter = "" if platform == 'All' else f"AND platform = '{platform}'"
    status_filter = _build_status_filter()

    query = f'''
        WITH daily_revenue AS (
            SELECT
                date,
                SUM(subtotal_net) as revenue,
                COUNT(DISTINCT order_id) as orders
            FROM orders
            WHERE date >= ? AND date <= ? {platform_filter} {status_filter}
            GROUP BY date
        ),
        ranked AS (
            SELECT *,
                PERCENT_RANK() OVER (ORDER BY revenue ASC) as percentile
            FROM daily_revenue
        )
        SELECT date, revenue, orders
        FROM ranked
        WHERE percentile > 0.2 AND percentile < 0.8
        ORDER BY ABS(percentile - 0.5) ASC
        LIMIT 3
    '''

    return conn.execute(query, [start_date, end_date]).fetchdf()


def query_middle3_aov_days(
    start_date: date,
    end_date: date,
    platform: str = 'All'
) -> pd.DataFrame:
    """Query middle 3 AOV days (Middle tier: 0.2 < PERCENT_RANK < 0.8)."""
    conn = get_connection()

    platform_filter = "" if platform == 'All' else f"AND platform = '{platform}'"
    status_filter = _build_status_filter()

    query = f'''
        WITH daily_aov AS (
            SELECT
                date,
                SUM(subtotal_net) as revenue,
                COUNT(DISTINCT order_id) as orders,
                CASE WHEN COUNT(DISTINCT order_id) > 0
                     THEN SUM(subtotal_net) * 1.0 / COUNT(DISTINCT order_id)
                     ELSE 0 END as aov
            FROM orders
            WHERE date >= ? AND date <= ? {platform_filter} {status_filter}
            GROUP BY date
            HAVING COUNT(DISTINCT order_id) > 0
        ),
        ranked AS (
            SELECT *,
                PERCENT_RANK() OVER (ORDER BY aov ASC) as percentile
            FROM daily_aov
        )
        SELECT date, revenue, orders, aov
        FROM ranked
        WHERE percentile > 0.2 AND percentile < 0.8
        ORDER BY ABS(percentile - 0.5) ASC
        LIMIT 3
    '''

    return conn.execute(query, [start_date, end_date]).fetchdf()


def query_middle3_order_days(
    start_date: date,
    end_date: date,
    platform: str = 'All'
) -> pd.DataFrame:
    """Query middle 3 order count days (Middle tier: 0.2 < PERCENT_RANK < 0.8)."""
    conn = get_connection()

    platform_filter = "" if platform == 'All' else f"AND platform = '{platform}'"
    status_filter = _build_status_filter()

    query = f'''
        WITH daily_orders AS (
            SELECT
                date,
                COUNT(DISTINCT order_id) as orders,
                SUM(subtotal_net) as revenue
            FROM orders
            WHERE date >= ? AND date <= ? {platform_filter} {status_filter}
            GROUP BY date
        ),
        ranked AS (
            SELECT *,
                PERCENT_RANK() OVER (ORDER BY orders ASC) as percentile
            FROM daily_orders
        )
        SELECT date, orders, revenue
        FROM ranked
        WHERE percentile > 0.2 AND percentile < 0.8
        ORDER BY ABS(percentile - 0.5) ASC
        LIMIT 3
    '''

    return conn.execute(query, [start_date, end_date]).fetchdf()


def query_middle3_products(
    start_date: date,
    end_date: date,
    platform: str = 'All'
) -> pd.DataFrame:
    """Query middle 3 products by revenue (Middle tier: 0.2 < PERCENT_RANK < 0.8)."""
    conn = get_connection()

    platform_filter = "" if platform == 'All' else f"AND platform = '{platform}'"
    status_filter = _build_status_filter()

    query = f'''
        WITH product_revenue AS (
            SELECT
                product_name,
                SUM(subtotal_net) as revenue,
                SUM(quantity) as quantity,
                COUNT(DISTINCT order_id) as orders
            FROM orders
            WHERE date >= ? AND date <= ? {platform_filter} {status_filter}
            GROUP BY product_name
        ),
        ranked AS (
            SELECT *,
                PERCENT_RANK() OVER (ORDER BY revenue ASC) as percentile
            FROM product_revenue
        )
        SELECT product_name, revenue, quantity, orders
        FROM ranked
        WHERE percentile > 0.2 AND percentile < 0.8
        ORDER BY ABS(percentile - 0.5) ASC
        LIMIT 3
    '''

    return conn.execute(query, [start_date, end_date]).fetchdf()


def query_middle3_products_by_orders(
    start_date: date,
    end_date: date,
    platform: str = 'All'
) -> pd.DataFrame:
    """Query middle 3 products by order count (Middle tier: 0.2 < PERCENT_RANK < 0.8)."""
    conn = get_connection()

    platform_filter = "" if platform == 'All' else f"AND platform = '{platform}'"
    status_filter = _build_status_filter()

    query = f'''
        WITH product_orders AS (
            SELECT
                product_name,
                COUNT(DISTINCT order_id) as orders,
                SUM(subtotal_net) as revenue,
                SUM(quantity) as quantity
            FROM orders
            WHERE date >= ? AND date <= ? {platform_filter} {status_filter}
            GROUP BY product_name
        ),
        ranked AS (
            SELECT *,
                PERCENT_RANK() OVER (ORDER BY orders ASC) as percentile
            FROM product_orders
        )
        SELECT product_name, orders, revenue, quantity
        FROM ranked
        WHERE percentile > 0.2 AND percentile < 0.8
        ORDER BY ABS(percentile - 0.5) ASC
        LIMIT 3
    '''

    return conn.execute(query, [start_date, end_date]).fetchdf()


# Import timedelta for comparison functions
from datetime import timedelta
