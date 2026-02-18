"""
Data processor module for DPLUS Dashboard.
Implements Min/Middle/Max segmentation logic.
"""

import pandas as pd
from typing import Dict
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    REVENUE_TOP_PERCENTILE,
    REVENUE_BOTTOM_PERCENTILE,
    AOV_HIGH_MULTIPLIER,
    AOV_LOW_MULTIPLIER,
    PRODUCT_REVENUE_TOP_PERCENTILE
)


# =============================================================================
# Segmentation Functions
# =============================================================================

def label_revenue_segment(amount: float, top_threshold: float, bottom_threshold: float) -> str:
    """
    Label a revenue amount as Max, Middle, or Min.

    Args:
        amount: The revenue amount to label
        top_threshold: 80th percentile threshold
        bottom_threshold: 20th percentile threshold

    Returns:
        'Max', 'Middle', or 'Min'
    """
    if pd.isna(amount):
        return 'Middle'

    if amount > top_threshold:
        return 'Max'
    elif amount < bottom_threshold:
        return 'Min'
    else:
        return 'Middle'


def label_aov_segment(aov: float, avg_aov: float) -> str:
    """
    Label an AOV value as Max, Middle, or Min.

    Args:
        aov: The AOV value to label
        avg_aov: Average AOV for reference

    Returns:
        'Max', 'Middle', or 'Min'
    """
    if pd.isna(aov) or avg_aov == 0:
        return 'Middle'

    if aov > (avg_aov * AOV_HIGH_MULTIPLIER):
        return 'Max'
    elif aov < (avg_aov * AOV_LOW_MULTIPLIER):
        return 'Min'
    else:
        return 'Middle'


def label_product_segment(revenue: float, quantity: int, rev_threshold: float, qty_median: float) -> str:
    """
    Label a product as Hero (Max), Volume (Min), or Core (Middle).

    Args:
        revenue: Total revenue for the product
        quantity: Total quantity sold
        rev_threshold: 67th percentile revenue threshold
        qty_median: Median quantity

    Returns:
        'Max (Hero)', 'Min (Volume)', or 'Middle (Core)'
    """
    if pd.isna(revenue):
        return 'Middle (Core)'

    if revenue >= rev_threshold:
        return 'Max (Hero)'
    elif quantity >= qty_median and revenue < rev_threshold:
        return 'Min (Volume)'
    else:
        return 'Middle (Core)'


# =============================================================================
# Processing Functions
# =============================================================================

def process_revenue_trends(
    df: pd.DataFrame,
    time_granularity: str = 'D',
    platform_filter: str = 'All'
) -> pd.DataFrame:
    """
    Process revenue data with time-based segmentation.

    Args:
        df: Cleaned dataframe
        time_granularity: 'D' (day), 'W' (week), 'M' (month), 'Q' (quarter)
        platform_filter: 'All', 'TikTok', or 'Shopee'

    Returns:
        Dataframe with revenue trends and segments
    """
    # Filter by platform
    if platform_filter != 'All':
        df = df[df['platform'] == platform_filter].copy()

    if df.empty:
        return pd.DataFrame()

    # Group by date and platform
    df['date'] = pd.to_datetime(df['created_at']).dt.date

    if time_granularity == 'D':
        df['period'] = df['date']
    elif time_granularity == 'W':
        df['period'] = pd.to_datetime(df['created_at']).dt.to_period('W').dt.start_time.dt.date
    elif time_granularity == 'M':
        df['period'] = pd.to_datetime(df['created_at']).dt.to_period('M').dt.start_time.dt.date
    elif time_granularity == 'Q':
        df['period'] = pd.to_datetime(df['created_at']).dt.to_period('Q').dt.start_time.dt.date
    else:
        df['period'] = df['date']

    # Aggregate revenue by period and platform
    revenue_trends = df.groupby(['period', 'platform']).agg({
        'subtotal_net': 'sum',
        'order_id': 'nunique',
        'quantity': 'sum'
    }).reset_index()

    revenue_trends.columns = ['period', 'platform', 'revenue', 'orders', 'quantity']

    # Calculate segments per platform
    revenue_trends['revenue_segment'] = 'Middle'

    for platform in revenue_trends['platform'].unique():
        mask = revenue_trends['platform'] == platform
        platform_data = revenue_trends.loc[mask, 'revenue']

        if len(platform_data) >= 5:  # Need enough data for percentiles
            top_threshold = platform_data.quantile(REVENUE_TOP_PERCENTILE)
            bottom_threshold = platform_data.quantile(REVENUE_BOTTOM_PERCENTILE)

            revenue_trends.loc[mask, 'revenue_segment'] = platform_data.apply(
                lambda x: label_revenue_segment(x, top_threshold, bottom_threshold)
            )

    return revenue_trends


def process_aov_analysis(
    df: pd.DataFrame,
    time_granularity: str = 'D',
    platform_filter: str = 'All'
) -> pd.DataFrame:
    """
    Process AOV (Average Order Value) data with segmentation.

    Args:
        df: Cleaned dataframe
        time_granularity: 'D', 'W', 'M', 'Q'
        platform_filter: 'All', 'TikTok', or 'Shopee'

    Returns:
        Dataframe with AOV data and segments
    """
    # Filter by platform
    if platform_filter != 'All':
        df = df[df['platform'] == platform_filter].copy()

    if df.empty:
        return pd.DataFrame()

    # Group by date and platform
    df['date'] = pd.to_datetime(df['created_at']).dt.date

    if time_granularity == 'D':
        df['period'] = df['date']
    elif time_granularity == 'W':
        df['period'] = pd.to_datetime(df['created_at']).dt.to_period('W').dt.start_time.dt.date
    elif time_granularity == 'M':
        df['period'] = pd.to_datetime(df['created_at']).dt.to_period('M').dt.start_time.dt.date
    elif time_granularity == 'Q':
        df['period'] = pd.to_datetime(df['created_at']).dt.to_period('Q').dt.start_time.dt.date
    else:
        df['period'] = df['date']

    # Calculate AOV by period and platform
    aov_data = df.groupby(['period', 'platform']).agg({
        'subtotal_net': 'sum',
        'order_id': 'nunique'
    }).reset_index()

    aov_data['aov'] = aov_data['subtotal_net'] / aov_data['order_id']
    aov_data.columns = ['period', 'platform', 'revenue', 'orders', 'aov']

    # Calculate segments per platform
    aov_data['aov_segment'] = 'Middle'

    for platform in aov_data['platform'].unique():
        mask = aov_data['platform'] == platform
        avg_aov = aov_data.loc[mask, 'aov'].mean()

        aov_data.loc[mask, 'aov_segment'] = aov_data.loc[mask, 'aov'].apply(
            lambda x: label_aov_segment(x, avg_aov)
        )

    return aov_data


def process_product_matrix(
    df: pd.DataFrame,
    platform_filter: str = 'All'
) -> pd.DataFrame:
    """
    Process product data for matrix visualization.

    Args:
        df: Cleaned dataframe
        platform_filter: 'All', 'TikTok', or 'Shopee'

    Returns:
        Dataframe with product metrics and segments
    """
    # Filter by platform
    if platform_filter != 'All':
        df = df[df['platform'] == platform_filter].copy()

    if df.empty:
        return pd.DataFrame()

    # Aggregate by product and platform — use subtotal_net for ALL platforms
    # (matches BigQuery reference queries which use SAFE_CAST(subtotal_net AS FLOAT64))
    product_data = df.groupby(['product_name', 'platform']).agg(
        revenue=('subtotal_net', 'sum'),
        quantity=('quantity', 'sum'),
        orders=('order_id', 'nunique')
    ).reset_index()

    # Calculate segments per platform using PERCENT_RANK thresholds from reference queries:
    # Max (Hero):        revenue_percentile >= 0.8  (top 20%)
    # Min (Volume/Low):  revenue_percentile <= 0.4  (bottom 40%)
    # Middle (Core):     everything else             (middle 40%)
    product_data['matrix_segment'] = 'Middle (Core)'

    for plat in product_data['platform'].unique():
        mask = product_data['platform'] == plat
        plat_revenues = product_data.loc[mask, 'revenue']

        if len(plat_revenues) > 1:
            # PERCENT_RANK equivalent: rank each product's revenue
            ranks = plat_revenues.rank(method='average', pct=True)
            product_data.loc[mask, 'matrix_segment'] = ranks.apply(
                lambda r: 'Max (Hero)' if r >= 0.8 else ('Min (Volume)' if r <= 0.4 else 'Middle (Core)')
            )
        elif len(plat_revenues) == 1:
            product_data.loc[mask, 'matrix_segment'] = 'Middle (Core)'

    return product_data


def process_portfolio_health(
    df: pd.DataFrame,
    platform_filter: str = 'All'
) -> Dict:
    """
    Process portfolio health metrics.

    Args:
        df: Cleaned dataframe
        platform_filter: 'All', 'TikTok', or 'Shopee'

    Returns:
        Dictionary with portfolio health data
    """
    product_data = process_product_matrix(df, platform_filter)

    if product_data.empty:
        return {
            'segments': {},
            'total_revenue': 0,
            'risk_level': 'Unknown',
            'recommendation': 'No data available'
        }

    # Calculate revenue by segment
    segment_revenue = product_data.groupby('matrix_segment')['revenue'].sum()
    total_revenue = segment_revenue.sum()

    segments = {}
    for segment in ['Max (Hero)', 'Middle (Core)', 'Min (Volume)']:
        revenue = segment_revenue.get(segment, 0)
        segments[segment] = {
            'revenue': revenue,
            'percentage': round(revenue / total_revenue * 100, 1) if total_revenue > 0 else 0
        }

    # Determine risk level and recommendation
    hero_pct = segments['Max (Hero)']['percentage']
    core_pct = segments['Middle (Core)']['percentage']

    if hero_pct > 60:
        risk_level = 'High'
        recommendation = 'High reliance on Hero products. Consider promoting Core products to diversify risk.'
    elif core_pct < 25:
        risk_level = 'Medium'
        recommendation = 'Core product segment is weak. Opportunity to push mid-tier products.'
    else:
        risk_level = 'Low'
        recommendation = 'Portfolio is well-balanced across segments.'

    return {
        'segments': segments,
        'total_revenue': total_revenue,
        'risk_level': risk_level,
        'recommendation': recommendation,
        'product_data': product_data
    }


def process_dashboard_data(
    df: pd.DataFrame,
    filters: Dict
) -> Dict:
    """
    Main processing function that generates all dashboard data.

    Args:
        df: Cleaned dataframe
        filters: Dictionary with filter settings

    Returns:
        Dictionary with all processed data for dashboard
    """
    # Apply date filter
    start_date = filters.get('start_date')
    end_date = filters.get('end_date')

    if start_date and end_date:
        df['date'] = pd.to_datetime(df['created_at']).dt.date
        df = df[(df['date'] >= start_date) & (df['date'] <= end_date)].copy()

    # Get filter settings
    time_granularity = filters.get('granularity', 'D')
    platform_filter = filters.get('platform', 'All')

    return {
        'revenue_trends': process_revenue_trends(df, time_granularity, platform_filter),
        'aov_analysis': process_aov_analysis(df, time_granularity, platform_filter),
        'product_matrix': process_product_matrix(df, platform_filter),
        'portfolio_health': process_portfolio_health(df, platform_filter),
        'filters_applied': {
            'start_date': start_date,
            'end_date': end_date,
            'granularity': time_granularity,
            'platform': platform_filter
        }
    }
