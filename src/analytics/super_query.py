"""
Super Query Analytics Module for DPLUS Dashboard.
Provides Min/Middle/Max segmentation for revenue, AOV, product matrix, and product mix.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import date


# =============================================================================
# Section 1: Revenue Over Time Analysis
# =============================================================================

def analyze_revenue_trend(df: pd.DataFrame) -> Dict:
    """
    Comprehensive revenue trend analysis with Min/Middle/Max segmentation.

    Args:
        df: DataFrame with columns [date, platform, revenue, orders, quantity]

    Returns:
        Dictionary containing:
        - trend_direction: 'up', 'down', 'stable'
        - trend_confidence: 0-100 confidence score
        - top_3_days: DataFrame with highest revenue days
        - low_anomaly_days: DataFrame with abnormally low revenue (z-score < -2)
        - segments: DataFrame with 'Max'/'Middle'/'Min' labels
        - segment_stats: Statistics for each segment
    """
    if df.empty:
        return {
            'trend_direction': 'stable',
            'trend_confidence': 0,
            'top_3_days': pd.DataFrame(),
            'low_anomaly_days': pd.DataFrame(),
            'segments': pd.DataFrame(),
            'segment_stats': {}
        }

    df = df.copy()

    # Calculate trend direction using linear regression
    if len(df) >= 3:
        x = np.arange(len(df))
        y = df['revenue'].values
        slope, _ = np.polyfit(x, y, 1)
        avg_revenue = df['revenue'].mean()

        if avg_revenue > 0:
            trend_pct = (slope * len(df)) / avg_revenue
            if trend_pct > 0.05:
                trend_direction = 'up'
                trend_confidence = min(100, int(abs(trend_pct) * 200))
            elif trend_pct < -0.05:
                trend_direction = 'down'
                trend_confidence = min(100, int(abs(trend_pct) * 200))
            else:
                trend_direction = 'stable'
                trend_confidence = 100 - int(abs(trend_pct) * 500)
        else:
            trend_direction = 'stable'
            trend_confidence = 50
    else:
        trend_direction = 'stable'
        trend_confidence = 50

    # Calculate percentiles for segmentation
    p80 = df['revenue'].quantile(0.80)
    p20 = df['revenue'].quantile(0.20)
    avg_revenue = df['revenue'].mean()
    std_revenue = df['revenue'].std()

    # Segment: Max=top 20%, Min=bottom 20%, Middle=rest
    def label_segment(revenue):
        if p80 == p20:  # All values are the same
            return 'Middle'
        if revenue >= p80:
            return 'Max'
        elif revenue <= p20:
            return 'Min'
        else:
            return 'Middle'

    df['segment'] = df['revenue'].apply(label_segment)

    # Calculate z-scores for anomaly detection
    if std_revenue > 0:
        df['z_score'] = (df['revenue'] - avg_revenue) / std_revenue
    else:
        df['z_score'] = 0

    # Get top 3 days by revenue
    top_3_days = df.nlargest(3, 'revenue')[['date', 'platform', 'revenue', 'orders', 'segment']].copy()

    # Get abnormally low days (z-score < -2)
    low_anomaly_days = df[df['z_score'] < -2][['date', 'platform', 'revenue', 'orders', 'z_score']].copy()

    # Calculate segment statistics
    segment_stats = {}
    for segment in ['Max', 'Middle', 'Min']:
        segment_df = df[df['segment'] == segment]
        if not segment_df.empty:
            segment_stats[segment] = {
                'count': len(segment_df),
                'total_revenue': segment_df['revenue'].sum(),
                'avg_revenue': segment_df['revenue'].mean(),
                'total_orders': segment_df['orders'].sum(),
                'pct_of_days': len(segment_df) / len(df) * 100
            }

    return {
        'trend_direction': trend_direction,
        'trend_confidence': max(0, min(100, trend_confidence)),
        'top_3_days': top_3_days,
        'low_anomaly_days': low_anomaly_days,
        'segments': df,
        'segment_stats': segment_stats,
        'thresholds': {
            'p80': p80,
            'p20': p20,
            'avg': avg_revenue
        }
    }


# =============================================================================
# Section 2: Average Order Value (AOV) Analysis
# =============================================================================

def analyze_aov(df: pd.DataFrame, orders_df: pd.DataFrame = None) -> Dict:
    """
    AOV analysis with Min/Middle/Max segmentation and activity context inference.

    Args:
        df: DataFrame with columns [date, platform, revenue, orders, aov]
        orders_df: Optional DataFrame with raw order data for activity inference

    Returns:
        Dictionary containing:
        - top_3_aov_days: DataFrame with highest AOV days
        - low_3_aov_days: DataFrame with lowest AOV days
        - segments: DataFrame with 'Max'/'Middle'/'Min' labels
        - activity_context: Dict mapping dates to inferred activities
        - segment_stats: Statistics for each segment
    """
    if df.empty:
        return {
            'top_3_aov_days': pd.DataFrame(),
            'low_3_aov_days': pd.DataFrame(),
            'segments': pd.DataFrame(),
            'activity_context': {},
            'segment_stats': {}
        }

    df = df.copy()

    # Calculate average AOV
    avg_aov = df['aov'].mean()

    # Define thresholds
    max_threshold = avg_aov * 1.2  # +20% above average
    min_threshold = avg_aov * 0.8  # -20% below average

    # Segment AOV
    def label_aov_segment(aov):
        if aov >= max_threshold:
            return 'Max'
        elif aov <= min_threshold:
            return 'Min'
        else:
            return 'Middle'

    df['segment'] = df['aov'].apply(label_aov_segment)

    # Get top 3 and bottom 3 AOV days
    top_3_aov_days = df.nlargest(3, 'aov')[['date', 'platform', 'aov', 'revenue', 'orders', 'segment']].copy()
    low_3_aov_days = df.nsmallest(3, 'aov')[['date', 'platform', 'aov', 'revenue', 'orders', 'segment']].copy()

    # Infer activity context if order data is provided
    activity_context = {}
    if orders_df is not None and not orders_df.empty:
        for _, row in pd.concat([top_3_aov_days, low_3_aov_days]).iterrows():
            date_val = row['date']
            activities = infer_activity_context(date_val, orders_df)
            activity_context[str(date_val)] = activities

    # Calculate segment statistics
    segment_stats = {}
    for segment in ['Max', 'Middle', 'Min']:
        segment_df = df[df['segment'] == segment]
        if not segment_df.empty:
            segment_stats[segment] = {
                'count': len(segment_df),
                'avg_aov': segment_df['aov'].mean(),
                'total_revenue': segment_df['revenue'].sum(),
                'total_orders': segment_df['orders'].sum(),
                'pct_of_days': len(segment_df) / len(df) * 100
            }

    return {
        'top_3_aov_days': top_3_aov_days,
        'low_3_aov_days': low_3_aov_days,
        'segments': df,
        'activity_context': activity_context,
        'segment_stats': segment_stats,
        'thresholds': {
            'avg_aov': avg_aov,
            'max_threshold': max_threshold,
            'min_threshold': min_threshold
        }
    }


def infer_activity_context(date_val, orders_df: pd.DataFrame) -> List[str]:
    """
    Infer what activity happened on a given date from order patterns.

    Detection rules:
    - Bundle day: >30% orders have 2+ different products
    - Livestream day: Order spike (>2x average hourly orders)
    - Promotion day: >40% orders have quantity > 1
    - Flash sale: High revenue in short time + high discount rate

    Args:
        date_val: The date to analyze
        orders_df: DataFrame with order data

    Returns:
        List of inferred activity types
    """
    activities = []

    # Filter orders for the specific date
    if 'date' in orders_df.columns:
        day_orders = orders_df[orders_df['date'] == date_val].copy()
    else:
        return ['Normal']

    if day_orders.empty:
        return ['Normal']

    # Check for bundles (multiple products per order)
    if 'order_id' in day_orders.columns and 'product_name' in day_orders.columns:
        order_product_counts = day_orders.groupby('order_id')['product_name'].nunique()
        if len(order_product_counts) > 0:
            bundle_rate = (order_product_counts > 1).mean()
            if bundle_rate > 0.3:
                activities.append('Bundle')

    # Check for livestream (order volume spike in short time)
    if 'created_at' in day_orders.columns and len(day_orders) > 5:
        try:
            hourly_orders = day_orders.groupby(
                pd.to_datetime(day_orders['created_at']).dt.hour
            ).size()
            if len(hourly_orders) > 0 and hourly_orders.mean() > 0:
                if hourly_orders.max() > hourly_orders.mean() * 2:
                    activities.append('Livestream')
        except:
            pass

    # Check for promotion (high quantity per order)
    if 'quantity' in day_orders.columns:
        high_qty_rate = (day_orders['quantity'] > 1).mean()
        if high_qty_rate > 0.4:
            activities.append('Promotion')

    # Check for flash sale (high discount rate)
    if 'subtotal_gross' in day_orders.columns and 'subtotal_net' in day_orders.columns:
        valid_orders = day_orders[day_orders['subtotal_gross'] > 0]
        if len(valid_orders) > 0:
            discount_rate = 1 - (valid_orders['subtotal_net'].sum() / valid_orders['subtotal_gross'].sum())
            if discount_rate > 0.3:  # More than 30% average discount
                activities.append('Flash Sale')

    return activities if activities else ['Normal']


# =============================================================================
# Section 3: Product Matrix (Revenue vs Quantity)
# =============================================================================

def analyze_product_matrix(df: pd.DataFrame) -> Dict:
    """
    Product matrix analysis categorizing products into Hero/Core/Volume segments.

    Args:
        df: DataFrame with columns [product_name, platform, revenue, quantity, orders]

    Returns:
        Dictionary containing:
        - segments: DataFrame with 'Hero'/'Core'/'Volume' labels
        - quadrant_distribution: Dict with counts per segment
        - top_hero_products: Top 5 hero products
        - top_volume_products: Top 5 volume products
        - segment_stats: Statistics for each segment
    """
    if df.empty:
        return {
            'segments': pd.DataFrame(),
            'quadrant_distribution': {},
            'top_hero_products': pd.DataFrame(),
            'top_volume_products': pd.DataFrame(),
            'segment_stats': {}
        }

    df = df.copy()

    # Calculate percentiles
    revenue_p67 = df['revenue'].quantile(0.67)
    revenue_p33 = df['revenue'].quantile(0.33)
    quantity_median = df['quantity'].median()

    # Categorize products
    def label_product_segment(row):
        if row['revenue'] >= revenue_p67:
            return 'Hero'  # High revenue = Hero products (Max)
        elif row['revenue'] <= revenue_p33 and row['quantity'] >= quantity_median:
            return 'Volume'  # Low revenue but high quantity = Volume products (Min)
        else:
            return 'Core'  # Everything else = Core products (Middle)

    df['segment'] = df.apply(label_product_segment, axis=1)

    # Get quadrant distribution
    quadrant_distribution = df['segment'].value_counts().to_dict()

    # Get top products from each segment
    hero_products = df[df['segment'] == 'Hero']
    volume_products = df[df['segment'] == 'Volume']

    top_hero_products = hero_products.nlargest(5, 'revenue')[
        ['product_name', 'platform', 'revenue', 'quantity', 'orders']
    ].copy() if not hero_products.empty else pd.DataFrame()

    top_volume_products = volume_products.nlargest(5, 'quantity')[
        ['product_name', 'platform', 'revenue', 'quantity', 'orders']
    ].copy() if not volume_products.empty else pd.DataFrame()

    # Calculate segment statistics
    segment_stats = {}
    for segment in ['Hero', 'Core', 'Volume']:
        segment_df = df[df['segment'] == segment]
        if not segment_df.empty:
            segment_stats[segment] = {
                'count': len(segment_df),
                'total_revenue': segment_df['revenue'].sum(),
                'avg_revenue': segment_df['revenue'].mean(),
                'total_quantity': segment_df['quantity'].sum(),
                'avg_quantity': segment_df['quantity'].mean(),
                'pct_of_products': len(segment_df) / len(df) * 100,
                'pct_of_revenue': segment_df['revenue'].sum() / df['revenue'].sum() * 100 if df['revenue'].sum() > 0 else 0
            }

    return {
        'segments': df,
        'quadrant_distribution': quadrant_distribution,
        'top_hero_products': top_hero_products,
        'top_volume_products': top_volume_products,
        'segment_stats': segment_stats,
        'thresholds': {
            'revenue_p67': revenue_p67,
            'revenue_p33': revenue_p33,
            'quantity_median': quantity_median
        }
    }


# =============================================================================
# Section 4: Product Mix Percentage (Portfolio Health)
# =============================================================================

def analyze_product_mix(df: pd.DataFrame) -> Dict:
    """
    Product mix analysis for portfolio health assessment.

    Risk Assessment:
    - Max (Hero) > 60%: HIGH RISK - Over-reliance on hero products
    - Middle (Core) < 25%: WARNING - Need to push core products
    - Otherwise: HEALTHY - Balanced portfolio

    Args:
        df: DataFrame with columns [product_name, segment, revenue, quantity]

    Returns:
        Dictionary containing:
        - mix_percentages: Dict with revenue percentage per segment
        - risk_level: 'Low', 'Medium', 'High'
        - risk_factors: List of risk factors identified
        - recommendations: List of actionable recommendations
    """
    if df.empty:
        return {
            'mix_percentages': {},
            'risk_level': 'Unknown',
            'risk_factors': [],
            'recommendations': []
        }

    total_revenue = df['revenue'].sum()

    if total_revenue == 0:
        return {
            'mix_percentages': {},
            'risk_level': 'Unknown',
            'risk_factors': ['No revenue data'],
            'recommendations': ['Add data to analyze']
        }

    # Calculate mix percentages
    mix_percentages = {}
    for segment in ['Hero', 'Core', 'Volume']:
        segment_revenue = df[df['segment'] == segment]['revenue'].sum()
        mix_percentages[segment] = (segment_revenue / total_revenue) * 100

    # Assess risk
    risk_factors = []
    recommendations = []
    risk_level = 'Low'

    hero_pct = mix_percentages.get('Hero', 0)
    core_pct = mix_percentages.get('Core', 0)
    volume_pct = mix_percentages.get('Volume', 0)

    # Check for over-reliance on hero products
    if hero_pct > 60:
        risk_level = 'High'
        risk_factors.append(f"Over-reliance on hero products: {hero_pct:.1f}% of revenue")
        recommendations.append("Diversify product portfolio - develop new core products")
        recommendations.append("Reduce dependency on top-selling products")
    elif hero_pct > 50:
        risk_level = 'Medium'
        risk_factors.append(f"High dependency on hero products: {hero_pct:.1f}% of revenue")
        recommendations.append("Consider expanding core product line")

    # Check for weak core products
    if core_pct < 25:
        if risk_level == 'Low':
            risk_level = 'Medium'
        risk_factors.append(f"Weak core product segment: only {core_pct:.1f}% of revenue")
        recommendations.append("Urgent: Push core products through marketing campaigns")
        recommendations.append("Consider bundling core products with hero products")

    # Check for volume products contribution
    if volume_pct < 10:
        risk_factors.append(f"Low volume product contribution: {volume_pct:.1f}% of revenue")
        recommendations.append("Consider volume-based promotions to increase sales")

    # If no risk factors, portfolio is healthy
    if not risk_factors:
        recommendations.append("Portfolio is well-balanced - maintain current strategy")
        recommendations.append("Continue monitoring product performance trends")

    return {
        'mix_percentages': mix_percentages,
        'risk_level': risk_level,
        'risk_factors': risk_factors,
        'recommendations': recommendations,
        'segment_breakdown': {
            'Hero': {'pct': hero_pct, 'status': 'High' if hero_pct > 60 else 'Normal'},
            'Core': {'pct': core_pct, 'status': 'Low' if core_pct < 25 else 'Normal'},
            'Volume': {'pct': volume_pct, 'status': 'Low' if volume_pct < 10 else 'Normal'}
        }
    }


# =============================================================================
# Comprehensive Super Query
# =============================================================================

def run_super_query(
    revenue_df: pd.DataFrame,
    product_df: pd.DataFrame,
    orders_df: pd.DataFrame = None
) -> Dict:
    """
    Run all super query analytics and return comprehensive results.

    Args:
        revenue_df: DataFrame with daily revenue data
        product_df: DataFrame with product performance data
        orders_df: Optional DataFrame with raw order data for activity inference

    Returns:
        Dictionary containing all analytics results
    """
    results = {}

    # Section 1: Revenue Over Time
    results['revenue_analysis'] = analyze_revenue_trend(revenue_df)

    # Section 2: AOV Analysis
    if 'aov' in revenue_df.columns:
        results['aov_analysis'] = analyze_aov(revenue_df, orders_df)
    else:
        # Calculate AOV if not present
        revenue_df_copy = revenue_df.copy()
        revenue_df_copy['aov'] = revenue_df_copy['revenue'] / revenue_df_copy['orders'].replace(0, 1)
        results['aov_analysis'] = analyze_aov(revenue_df_copy, orders_df)

    # Section 3: Product Matrix
    product_matrix_result = analyze_product_matrix(product_df)
    results['product_matrix'] = product_matrix_result

    # Section 4: Product Mix (using segments from product matrix)
    if not product_matrix_result['segments'].empty:
        results['product_mix'] = analyze_product_mix(product_matrix_result['segments'])
    else:
        results['product_mix'] = {
            'mix_percentages': {},
            'risk_level': 'Unknown',
            'risk_factors': [],
            'recommendations': []
        }

    return results
