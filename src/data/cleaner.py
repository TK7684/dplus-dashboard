"""
Data cleaner module for DPLUS Dashboard.
Standardizes, cleans, and filters the raw data.
"""

import pandas as pd
from typing import Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BLACKLIST_KEYWORDS


def parse_tiktok_date(date_str: str) -> Optional[pd.Timestamp]:
    """Parse TikTok date format: DD/MM/YYYY HH:MM:SS"""
    if pd.isna(date_str) or date_str == '':
        return None

    try:
        # TikTok format: 16/02/2026 08:55:18
        return pd.to_datetime(date_str, format='%d/%m/%Y %H:%M:%S')
    except Exception:
        try:
            return pd.to_datetime(date_str, dayfirst=True)
        except Exception:
            return None


def parse_shopee_date(date_str: str) -> Optional[pd.Timestamp]:
    """Parse Shopee date format: YYYY-MM-DD HH:MM"""
    if pd.isna(date_str) or date_str == '':
        return None

    try:
        # Shopee format: 2026-02-01 00:16
        return pd.to_datetime(date_str, format='%Y-%m-%d %H:%M')
    except Exception:
        try:
            return pd.to_datetime(date_str)
        except Exception:
            return None


def clean_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Parse and standardize dates for both platforms."""
    df = df.copy()

    # Parse dates based on platform
    tiktok_mask = df['platform'] == 'TikTok'
    shopee_mask = df['platform'] == 'Shopee'

    # Parse TikTok dates
    if tiktok_mask.any():
        df.loc[tiktok_mask, 'created_at'] = df.loc[tiktok_mask, 'created_at'].apply(parse_tiktok_date)

    # Parse Shopee dates
    if shopee_mask.any():
        df.loc[shopee_mask, 'created_at'] = df.loc[shopee_mask, 'created_at'].apply(parse_shopee_date)

    return df


def clean_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Convert numeric columns to proper types."""
    df = df.copy()

    numeric_cols = ['order_total_amount', 'quantity', 'subtotal_net']

    for col in numeric_cols:
        if col in df.columns:
            # Convert to numeric, coercing errors to NaN
            df[col] = pd.to_numeric(df[col], errors='coerce')
            # Fill NaN with 0
            df[col] = df[col].fillna(0)

    return df


def is_blacklisted(product_name: str) -> bool:
    """Check if a product name contains blacklisted keywords."""
    if pd.isna(product_name) or product_name == '':
        return False

    product_lower = str(product_name).lower()

    for keyword in BLACKLIST_KEYWORDS:
        if keyword.lower() in product_lower:
            return True

    return False


def filter_blacklisted_products(df: pd.DataFrame) -> pd.DataFrame:
    """Remove rows with blacklisted products."""
    if 'product_name' not in df.columns:
        return df

    df = df.copy()

    # Create mask for non-blacklisted products
    mask = ~df['product_name'].apply(is_blacklisted)

    # Count filtered rows
    filtered_count = len(df) - mask.sum()
    if filtered_count > 0:
        print(f"Filtered out {filtered_count} blacklisted product rows")

    return df[mask].reset_index(drop=True)


def clean_product_names(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and standardize product names."""
    if 'product_name' not in df.columns:
        return df

    df = df.copy()

    # Strip whitespace
    df['product_name'] = df['product_name'].str.strip()

    # Replace multiple spaces with single space
    df['product_name'] = df['product_name'].str.replace(r'\s+', ' ', regex=True)

    return df


def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Remove duplicate rows based on order_id and product_name."""
    df = df.copy()

    # Keep the first occurrence of duplicates
    initial_count = len(df)
    df = df.drop_duplicates(subset=['order_id', 'product_name', 'platform'], keep='first')
    final_count = len(df)

    if initial_count != final_count:
        print(f"Removed {initial_count - final_count} duplicate rows")

    return df.reset_index(drop=True)


def handle_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """Handle missing values in the dataframe."""
    df = df.copy()

    # Fill missing product names
    if 'product_name' in df.columns:
        df['product_name'] = df['product_name'].fillna('Unknown Product')

    # Fill missing seller SKU
    if 'seller_sku' in df.columns:
        df['seller_sku'] = df['seller_sku'].fillna('')

    # Fill missing order status
    if 'order_status' in df.columns:
        df['order_status'] = df['order_status'].fillna('Unknown')

    return df


def clean_data(df: pd.DataFrame, filter_blacklist: bool = True) -> pd.DataFrame:
    """
    Main cleaning function that applies all cleaning steps.

    Args:
        df: Raw dataframe from loader
        filter_blacklist: Whether to filter out blacklisted products

    Returns:
        Cleaned dataframe
    """
    if df.empty:
        return df

    # Apply cleaning steps in order
    df = clean_dates(df)
    df = clean_numeric_columns(df)
    df = clean_product_names(df)
    df = handle_missing_values(df)

    if filter_blacklist:
        df = filter_blacklisted_products(df)

    df = remove_duplicates(df)

    # Remove rows with invalid dates
    df = df[df['created_at'].notna()].reset_index(drop=True)

    # Sort by date
    df = df.sort_values('created_at').reset_index(drop=True)

    return df


def get_cleaning_summary(df_before: pd.DataFrame, df_after: pd.DataFrame) -> dict:
    """Get summary of cleaning operations."""
    return {
        'rows_before': len(df_before),
        'rows_after': len(df_after),
        'rows_removed': len(df_before) - len(df_after),
        'removal_percentage': round((len(df_before) - len(df_after)) / len(df_before) * 100, 2) if len(df_before) > 0 else 0
    }
