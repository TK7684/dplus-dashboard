"""
Configuration constants for DPLUS Dashboard.
Soft UI Evolution theme for skincare & wellness brand.
"""

# =============================================================================
# Color Palette - Soft UI Evolution (Skincare Theme)
# =============================================================================
COLORS = {
    # Segments - Soft, wellness-inspired colors
    'Max': '#10B981',       # Emerald green (growth, success)
    'Middle': '#6366F1',    # Indigo (neutral)
    'Min': '#F97316',       # Warm orange (attention)

    # Platforms
    'TikTok': '#1E293B',    # Slate dark
    'Shopee': '#EF4444',    # Coral red (Shopee brand)

    # UI Colors - Soft UI Evolution
    'Primary': '#4A7C6F',    # Sage green
    'Secondary': '#60A5FA',  # Soft blue
    'Accent': '#F97316',     # CTA orange
    'Background': '#F8FAFC',  # Cool white
    'Card': '#FFFFFF',       # Pure white
    'CardHover': '#F1F5F9',  # Light hover
    'Border': '#E2E8F0',     # Soft border
    'Text': '#1E293B',       # Slate dark
    'TextLight': '#475569',  # Slate medium (darker for readability)
    'TextMuted': '#64748B',  # Slate (dark enough to read)
    'TextSection': '#374151',  # Dark gray for section headers

    # Shadow colors
    'ShadowLight': 'rgba(0, 0, 0, 0.04)',
    'ShadowMedium': 'rgba(0, 0, 0, 0.08)',
    'ShadowDark': 'rgba(0, 0, 0, 0.12)',
}

# =============================================================================
# Typography
# =============================================================================
TYPOGRAPHY = {
    'FontPrimary': 'Inter',
    'FontDisplay': 'Inter',
    'FontMono': 'Fira Code',
    'SizeXS': '0.75rem',
    'SizeSM': '0.875rem',
    'SizeBase': '1rem',
    'SizeLG': '1.125rem',
    'SizeXL': '1.25rem',
    'Size2XL': '1.5rem',
    'Size3XL': '2rem',
}

# =============================================================================
# Effects & Animations
# =============================================================================
EFFECTS = {
    'TransitionFast': '150ms',
    'TransitionNormal': '250ms',
    'TransitionSlow': '350ms',
    'RadiusSM': '8px',
    'RadiusMD': '12px',
    'RadiusLG': '16px',
    'RadiusXL': '24px',
}

# =============================================================================
# Product Blacklist (Non-Skincare/Supplement items to exclude)
# Case-insensitive matching - excludes apple, iphone, ipad products
# =============================================================================
BLACKLIST_KEYWORDS = [
    'apple', 'iphone', 'ipad', 'macbook', 'airpods', 'apple watch',
    'samsung', 'galaxy', 'case', 'charger', 'cable', 'headphone',
    'earphone', 'earbuds', 'electronics', 'accessories', 'adapter',
    'tempered glass', 'screen protector', 'phone cover', 'phone case',
    'wireless charger', 'power bank', 'usb', 'lightning', 'type-c'
]

# =============================================================================
# Column Mappings
# =============================================================================

# TikTok columns (English) -> Standardized field names
TIKTOK_COLUMN_MAP = {
    'Order ID': 'order_id',
    'Order Amount': 'order_total_amount',
    'Created Time': 'created_at',
    'Product Name': 'product_name',
    'Quantity': 'quantity',
    'SKU Subtotal After Discount': 'subtotal_net',
    'Product Category': 'product_category',
    'Order Status': 'order_status',
    'Seller SKU': 'seller_sku'
}

# Shopee columns (Thai) -> Standardized field names
SHOPEE_COLUMN_MAP = {
    'หมายเลขคำสั่งซื้อ': 'order_id',
    'จำนวนเงินทั้งหมด': 'order_total_amount',
    'วันที่ทำการสั่งซื้อ': 'created_at',
    'ชื่อสินค้า': 'product_name',
    'จำนวน': 'quantity',
    'ราคาขายสุทธิ': 'subtotal_net',
    'สถานะการสั่งซื้อ': 'order_status',
    'เลขอ้างอิง SKU (SKU Reference No.)': 'seller_sku'
}

# Final standardized columns to keep
STANDARD_COLUMNS = [
    'order_id',
    'order_total_amount',
    'created_at',
    'product_name',
    'quantity',
    'subtotal_net',
    'platform',
    'order_status',
    'seller_sku'
]

# =============================================================================
# Segmentation Thresholds
# =============================================================================
REVENUE_TOP_PERCENTILE = 0.80
REVENUE_BOTTOM_PERCENTILE = 0.20

AOV_HIGH_MULTIPLIER = 1.2
AOV_LOW_MULTIPLIER = 0.8

PRODUCT_REVENUE_TOP_PERCENTILE = 0.67

# =============================================================================
# Data Paths
# =============================================================================
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Local data directory (not in git) - for development
DATA_DIR = os.path.join(PROJECT_ROOT, 'Original files')

# Cloud data directory (included in git for deployment)
# Check if running in Hugging Face Spaces or similar cloud environment
CLOUD_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'uploaded')

# Also check for data in project root data folder
ALT_DATA_DIR = os.path.join(PROJECT_ROOT, 'data')

TIKTOK_PATTERN = 'ทั้งหมด คำสั่งซื้อ-*.csv'
SHOPEE_PATTERN = 'Order.all.*.xlsx'
