"""
Data loader module for DPLUS Dashboard.
Loads TikTok CSV and Shopee Excel files.
"""

import os
import glob
import pandas as pd
import streamlit as st
from typing import List
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    DATA_DIR,
    TIKTOK_PATTERN,
    SHOPEE_PATTERN,
    TIKTOK_COLUMN_MAP,
    SHOPEE_COLUMN_MAP,
    STANDARD_COLUMNS
)


def get_tiktok_files() -> List[str]:
    """Get list of TikTok CSV files."""
    pattern = os.path.join(DATA_DIR, TIKTOK_PATTERN)
    files = glob.glob(pattern)
    return sorted(files)


def get_shopee_files() -> List[str]:
    """Get list of Shopee Excel files."""
    pattern = os.path.join(DATA_DIR, SHOPEE_PATTERN)
    files = glob.glob(pattern)
    return sorted(files)


def load_tiktok_file(filepath: str) -> pd.DataFrame:
    """Load a single TikTok CSV file."""
    try:
        # TikTok CSVs may have different encodings
        df = pd.read_csv(filepath, encoding='utf-8')
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(filepath, encoding='utf-8-sig')
        except UnicodeDecodeError:
            df = pd.read_csv(filepath, encoding='latin-1')

    # Strip whitespace from column names
    df.columns = df.columns.str.strip()

    # Select and rename columns
    available_cols = [c for c in TIKTOK_COLUMN_MAP.keys() if c in df.columns]
    df = df[available_cols].copy()
    df = df.rename(columns=TIKTOK_COLUMN_MAP)

    df['platform'] = 'TikTok'

    return df


def load_shopee_file(filepath: str) -> pd.DataFrame:
    """Load a single Shopee Excel file."""
    df = pd.read_excel(filepath)

    # Select and rename columns
    available_cols = [c for c in SHOPEE_COLUMN_MAP.keys() if c in df.columns]
    df = df[available_cols].copy()
    df = df.rename(columns=SHOPEE_COLUMN_MAP)

    df['platform'] = 'Shopee'

    return df


@st.cache_data(ttl=3600, show_spinner=False)
def load_all_tiktok_files() -> pd.DataFrame:
    """Load and combine all TikTok CSV files."""
    files = get_tiktok_files()

    if not files:
        return pd.DataFrame(columns=STANDARD_COLUMNS)

    dfs = []
    progress_bar = st.progress(0, text="Loading TikTok files...")

    for i, filepath in enumerate(files):
        try:
            df = load_tiktok_file(filepath)
            dfs.append(df)
        except Exception as e:
            st.warning(f"Could not load {os.path.basename(filepath)}: {e}")

        progress_bar.progress((i + 1) / len(files), text=f"Loading TikTok file {i+1}/{len(files)}")

    progress_bar.empty()

    if not dfs:
        return pd.DataFrame(columns=STANDARD_COLUMNS)

    combined = pd.concat(dfs, ignore_index=True)
    return combined


@st.cache_data(ttl=3600, show_spinner=False)
def load_all_shopee_files() -> pd.DataFrame:
    """Load and combine all Shopee Excel files."""
    files = get_shopee_files()

    if not files:
        return pd.DataFrame(columns=STANDARD_COLUMNS)

    dfs = []
    progress_bar = st.progress(0, text="Loading Shopee files...")

    for i, filepath in enumerate(files):
        try:
            df = load_shopee_file(filepath)
            dfs.append(df)
        except Exception as e:
            st.warning(f"Could not load {os.path.basename(filepath)}: {e}")

        progress_bar.progress((i + 1) / len(files), text=f"Loading Shopee file {i+1}/{len(files)}")

    progress_bar.empty()

    if not dfs:
        return pd.DataFrame(columns=STANDARD_COLUMNS)

    combined = pd.concat(dfs, ignore_index=True)
    return combined


@st.cache_data(ttl=3600)
def load_all_data() -> pd.DataFrame:
    """Load and combine all data from both platforms."""
    # Load both platforms
    tiktok_df = load_all_tiktok_files()
    shopee_df = load_all_shopee_files()

    # Combine
    if tiktok_df.empty and shopee_df.empty:
        return pd.DataFrame(columns=STANDARD_COLUMNS)
    elif tiktok_df.empty:
        combined = shopee_df
    elif shopee_df.empty:
        combined = tiktok_df
    else:
        combined = pd.concat([tiktok_df, shopee_df], ignore_index=True)

    return combined


def get_data_summary(df: pd.DataFrame) -> dict:
    """Get summary statistics of loaded data."""
    if df.empty:
        return {
            'total_rows': 0,
            'tiktok_rows': 0,
            'shopee_rows': 0,
            'date_range': 'No data',
            'total_revenue': 0,
            'unique_products': 0
        }

    summary = {
        'total_rows': len(df),
        'tiktok_rows': len(df[df['platform'] == 'TikTok']) if 'platform' in df.columns else 0,
        'shopee_rows': len(df[df['platform'] == 'Shopee']) if 'platform' in df.columns else 0,
        'date_range': 'Unknown',
        'total_revenue': df['order_total_amount'].sum() if 'order_total_amount' in df.columns else 0,
        'unique_products': df['product_name'].nunique() if 'product_name' in df.columns else 0
    }

    if 'created_at' in df.columns:
        try:
            dates = pd.to_datetime(df['created_at'], errors='coerce')
            min_date = dates.min()
            max_date = dates.max()
            if pd.notna(min_date) and pd.notna(max_date):
                summary['date_range'] = f"{min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}"
        except Exception:
            pass

    return summary
