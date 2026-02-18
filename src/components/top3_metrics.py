"""
Top 3 Metrics component for DPLUS Dashboard.
Displays key insights including top/middle/bottom performers for revenue, AOV, and orders.
"""

import streamlit as st
import pandas as pd
from datetime import date
from typing import Dict, Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import COLORS
from data.database import (
    query_top3_revenue_days,
    query_bottom3_revenue_days,
    query_top3_aov_days,
    query_bottom3_aov_days,
    query_top3_order_days,
    query_bottom3_order_days,
    query_top3_products,
    query_top3_products_by_orders,
    query_middle3_revenue_days,
    query_middle3_aov_days,
    query_middle3_order_days,
    query_middle3_products,
    query_middle3_products_by_orders,
)


def render_top3_metrics(
    start_date: date,
    end_date: date,
    platform: str = 'All',
    title: str = "Top 3 Insights"
) -> None:
    """
    Render Top 3 metrics section with various insights.
    
    Args:
        start_date: Start of the period
        end_date: End of the period
        platform: Platform filter ('All', 'TikTok', 'Shopee')
        title: Section title
    """
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, rgba(74, 124, 111, 0.05) 0%, rgba(96, 165, 250, 0.05) 100%);
        border: 1px solid rgba(74, 124, 111, 0.15);
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
    ">
        <h3 style="
            color: {COLORS['Primary']};
            font-size: 1.1rem;
            font-weight: 700;
            margin: 0 0 1rem 0;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        ">
            <span>📊</span>
            <span>{title}</span>
        </h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Query all Top 3, Middle 3, and Bottom 3 data
    try:
        # Revenue data
        top_revenue = query_top3_revenue_days(start_date, end_date, platform)
        middle_revenue = query_middle3_revenue_days(start_date, end_date, platform)
        bottom_revenue = query_bottom3_revenue_days(start_date, end_date, platform)
        
        # AOV data
        top_aov = query_top3_aov_days(start_date, end_date, platform)
        middle_aov = query_middle3_aov_days(start_date, end_date, platform)
        bottom_aov = query_bottom3_aov_days(start_date, end_date, platform)
        
        # Order count data
        top_orders = query_top3_order_days(start_date, end_date, platform)
        middle_orders = query_middle3_order_days(start_date, end_date, platform)
        bottom_orders = query_bottom3_order_days(start_date, end_date, platform)
        
        # Product data
        top_products = query_top3_products(start_date, end_date, platform)
        middle_products = query_middle3_products(start_date, end_date, platform)
        top_products_orders = query_top3_products_by_orders(start_date, end_date, platform)
        middle_products_orders = query_middle3_products_by_orders(start_date, end_date, platform)
    except Exception as e:
        st.warning(f"Unable to load Top 3 metrics: {e}")
        return
    
    # Create tabs for each metric category
    tab1, tab2, tab3, tab4 = st.tabs([
        "💰 Revenue Days", "💵 AOV Days", "📦 Order Days", "🛍️ Products"
    ])
    
    # Tab 1: Revenue Days
    with tab1:
        st.markdown("### Revenue Performance by Day")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            _render_metric_card(
                "🥇 Top 3 (Max)",
                top_revenue,
                'date',
                'revenue',
                format_value=lambda x: f"฿{x:,.0f}",
                color=COLORS['Max'],
                rank_emojis=['🥇', '🥈', '🥉']
            )
        
        with col2:
            _render_metric_card(
                "1️⃣2️⃣3️⃣ Middle 3",
                middle_revenue,
                'date',
                'revenue',
                format_value=lambda x: f"฿{x:,.0f}",
                color=COLORS['Middle'],
                rank_emojis=['1️⃣', '2️⃣', '3️⃣']
            )
        
        with col3:
            _render_metric_card(
                "🔻 Bottom 3 (Min)",
                bottom_revenue,
                'date',
                'revenue',
                format_value=lambda x: f"฿{x:,.0f}",
                color=COLORS['Min'],
                rank_emojis=['🔻', '🔻', '🔻']
            )
    
    # Tab 2: AOV Days
    with tab2:
        st.markdown("### Average Order Value by Day")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            _render_metric_card(
                "🥇 Top 3 (Max)",
                top_aov,
                'date',
                'aov',
                format_value=lambda x: f"฿{x:,.0f}",
                color=COLORS['Max'],
                rank_emojis=['🥇', '🥈', '🥉']
            )
        
        with col2:
            _render_metric_card(
                "1️⃣2️⃣3️⃣ Middle 3",
                middle_aov,
                'date',
                'aov',
                format_value=lambda x: f"฿{x:,.0f}",
                color=COLORS['Middle'],
                rank_emojis=['1️⃣', '2️⃣', '3️⃣']
            )
        
        with col3:
            _render_metric_card(
                "🔻 Bottom 3 (Min)",
                bottom_aov,
                'date',
                'aov',
                format_value=lambda x: f"฿{x:,.0f}",
                color=COLORS['Min'],
                rank_emojis=['🔻', '🔻', '🔻']
            )
    
    # Tab 3: Order Days
    with tab3:
        st.markdown("### Order Count by Day")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            _render_metric_card(
                "🥇 Top 3 (Max)",
                top_orders,
                'date',
                'orders',
                format_value=lambda x: f"{x:,} orders",
                color=COLORS['Max'],
                rank_emojis=['🥇', '🥈', '🥉']
            )
        
        with col2:
            _render_metric_card(
                "1️⃣2️⃣3️⃣ Middle 3",
                middle_orders,
                'date',
                'orders',
                format_value=lambda x: f"{x:,} orders",
                color=COLORS['Middle'],
                rank_emojis=['1️⃣', '2️⃣', '3️⃣']
            )
        
        with col3:
            _render_metric_card(
                "🔻 Bottom 3 (Min)",
                bottom_orders,
                'date',
                'orders',
                format_value=lambda x: f"{x:,} orders",
                color=COLORS['Min'],
                rank_emojis=['🔻', '🔻', '🔻']
            )
    
    # Tab 4: Products
    with tab4:
        st.markdown("### Product Performance")
        
        # Products by Revenue
        st.markdown("#### 💰 Products by Revenue")
        col1, col2 = st.columns(2)
        
        with col1:
            _render_metric_card(
                "🥇 Top 3 (Max)",
                top_products,
                'product_name',
                'revenue',
                format_value=lambda x: f"฿{x:,.0f}",
                color=COLORS['Max'],
                rank_emojis=['🥇', '🥈', '🥉'],
                max_label_length=30
            )
        
        with col2:
            _render_metric_card(
                "1️⃣2️⃣3️⃣ Middle 3",
                middle_products,
                'product_name',
                'revenue',
                format_value=lambda x: f"฿{x:,.0f}",
                color=COLORS['Middle'],
                rank_emojis=['1️⃣', '2️⃣', '3️⃣'],
                max_label_length=30
            )
        
        st.markdown("---")
        
        # Products by Orders
        st.markdown("#### 🛒 Products by Orders")
        col3, col4 = st.columns(2)
        
        with col3:
            _render_metric_card(
                "🥇 Top 3 (Max)",
                top_products_orders,
                'product_name',
                'orders',
                format_value=lambda x: f"{x:,} orders",
                color=COLORS['Max'],
                rank_emojis=['🥇', '🥈', '🥉'],
                max_label_length=30
            )
        
        with col4:
            _render_metric_card(
                "1️⃣2️⃣3️⃣ Middle 3",
                middle_products_orders,
                'product_name',
                'orders',
                format_value=lambda x: f"{x:,} orders",
                color=COLORS['Middle'],
                rank_emojis=['1️⃣', '2️⃣', '3️⃣'],
                max_label_length=30
            )


def _render_metric_card(
    title: str,
    data: pd.DataFrame,
    label_col: str,
    value_col: str,
    format_value,
    color: str,
    rank_emojis: Optional[list] = None,
    max_label_length: Optional[int] = None
) -> None:
    """Render a single metric card with items."""
    if rank_emojis is None:
        rank_emojis = ['🥇', '🥈', '🥉']
    
    st.markdown(f"""
    <div style="
        background: {COLORS['Card']};
        border: 1px solid {COLORS['Border']};
        border-radius: 12px;
        padding: 1rem;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
        height: 100%;
    ">
        <div style="
            font-size: 0.85rem;
            font-weight: 600;
            color: {COLORS['TextLight']};
            margin-bottom: 0.75rem;
        ">
            {title}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if data.empty:
        st.markdown(f"""
        <div style="
            color: {COLORS['TextMuted']};
            font-size: 0.8rem;
            font-style: italic;
        ">
            No data available
        </div>
        """, unsafe_allow_html=True)
        return
    
    for idx, row in data.iterrows():
        label = row[label_col]
        value = row[value_col]
        
        # Format date if it's a date column
        if label_col == 'date' and hasattr(label, 'strftime'):
            label = label.strftime('%Y-%m-%d')
        # Truncate long product names
        elif max_label_length and len(str(label)) > max_label_length:
            label = str(label)[:max_label_length] + '...'
        
        rank_emoji = rank_emojis[idx] if idx < len(rank_emojis) else f"{idx + 1}."
        
        st.markdown(f"""
        <div style="
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.5rem 0;
            border-bottom: 1px solid {COLORS['Border']};
        ">
            <div style="
                display: flex;
                align-items: center;
                gap: 0.5rem;
                flex: 1;
            ">
                <span style="font-size: 0.9rem;">{rank_emoji}</span>
                <span style="
                    font-size: 0.8rem;
                    color: {COLORS['Text']};
                    font-weight: 500;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                ">{label}</span>
            </div>
            <span style="
                font-size: 0.8rem;
                color: {color};
                font-weight: 700;
            ">{format_value(value)}</span>
        </div>
        """, unsafe_allow_html=True)
