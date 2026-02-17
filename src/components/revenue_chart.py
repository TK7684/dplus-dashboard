"""
Revenue Trends chart component.
"""

import plotly.graph_objects as go
import pandas as pd
import streamlit as st
from typing import Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import COLORS
from data.time_utils import calculate_change


def render_revenue_chart(
    current_data: pd.DataFrame,
    previous_data: Optional[pd.DataFrame] = None,
    show_comparison: bool = False
):
    """Render the revenue trends chart with Soft UI style."""

    if current_data.empty:
        st.info("No revenue data available for the selected period.")
        return

    fig = go.Figure()
    platforms = current_data['platform'].unique()

    # Platform colors - use theme colors instead of black
    platform_colors = {
        'TikTok': '#4A7C6F',  # Sage green
        'Shopee': '#E85A4F'   # Coral
    }

    # Current period traces
    for platform in platforms:
        platform_data = current_data[current_data['platform'] == platform].copy()
        platform_data = platform_data.sort_values('period')

        platform_color = platform_colors.get(platform, COLORS['Primary'])

        marker_colors = platform_data['revenue_segment'].map({
            'Max': COLORS['Max'],
            'Middle': COLORS['Middle'],
            'Min': COLORS['Min']
        })

        fig.add_trace(go.Scatter(
            x=platform_data['period'],
            y=platform_data['revenue'],
            mode='lines+markers',
            name=platform,
            line=dict(color=platform_color, width=2.5, shape='spline'),
            marker=dict(size=10, color=marker_colors, line=dict(width=2, color='white')),
            hovertemplate='<b>%{x}</b><br>Revenue: %{y:,.0f}<br>Orders: %{customdata[0]:,}<extra></extra>',
            customdata=platform_data[['orders']].values
        ))

    # Previous period traces (dashed)
    if show_comparison and previous_data is not None and not previous_data.empty:
        for platform in platforms:
            platform_data = previous_data[previous_data['platform'] == platform].copy()
            platform_data = platform_data.sort_values('period')

            platform_color = platform_colors.get(platform, COLORS['Primary'])

            fig.add_trace(go.Scatter(
                x=platform_data['period'],
                y=platform_data['revenue'],
                mode='lines',
                name=f'{platform} (prev)',
                line=dict(color=platform_color, width=1.5, dash='dot', shape='spline'),
                opacity=0.4,
                hovertemplate='<b>%{x}</b><br>Previous: %{y:,.0f}<extra></extra>'
            ))

    fig.update_layout(
        height=350,
        margin=dict(l=10, r=10, t=10, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode='x unified',
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color=COLORS['Text']),
        xaxis=dict(
            showgrid=True,
            gridcolor=COLORS['Border'],
            gridwidth=0.5,
            linecolor=COLORS['Border'],
            tickfont=dict(color=COLORS['TextLight'])
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=COLORS['Border'],
            gridwidth=0.5,
            linecolor=COLORS['Border'],
            tickfont=dict(color=COLORS['TextLight'])
        )
    )

    st.plotly_chart(fig, width="stretch")

    # Summary row
    total_revenue = current_data['revenue'].sum()
    total_orders = current_data['orders'].sum()
    max_days = len(current_data[current_data['revenue_segment'] == 'Max'])
    min_days = len(current_data[current_data['revenue_segment'] == 'Min'])

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if show_comparison and previous_data is not None and not previous_data.empty:
            prev = previous_data['revenue'].sum()
            change = calculate_change(total_revenue, prev)
            st.metric("Total Revenue", f"{total_revenue:,.0f}", delta=f"{change['percentage']:+.1f}%")
        else:
            st.metric("Total Revenue", f"{total_revenue:,.0f}")

    with col2:
        st.metric("Orders", f"{total_orders:,}")

    with col3:
        st.metric("High Days", f"{max_days}")

    with col4:
        st.metric("Low Days", f"{min_days}")

    # Insights section
    st.markdown("---")
    render_revenue_insights(current_data)


def render_revenue_insights(df: pd.DataFrame):
    """Render revenue insights with top/low performing days."""
    if df.empty:
        return

    # Get top 3 highest revenue days
    top_days = df.nlargest(3, 'revenue')[['period', 'revenue', 'orders', 'platform']].copy()
    top_days['period'] = top_days['period'].astype(str)

    # Get bottom 3 lowest revenue days
    low_days = df.nsmallest(3, 'revenue')[['period', 'revenue', 'orders', 'platform']].copy()
    low_days['period'] = low_days['period'].astype(str)

    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(74, 124, 111, 0.05) 0%, rgba(96, 165, 250, 0.05) 100%);
                border: 1px solid {COLORS['Border']}; border-radius: 12px; padding: 1rem; margin-top: 0.5rem;">
        <div style="font-size: 0.75rem; font-weight: 600; color: {COLORS['TextSection']}; margin-bottom: 0.75rem;
             text-transform: uppercase; letter-spacing: 0.5px;">Segment Definitions</div>
        <div style="display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1rem;">
            <div style="display: flex; align-items: center; gap: 6px;">
                <div style="width: 10px; height: 10px; background: {COLORS['Max']}; border-radius: 3px;"></div>
                <span style="font-size: 0.8rem; color: {COLORS['Text']};"><b>Max:</b> Top 20% highest revenue days</span>
            </div>
            <div style="display: flex; align-items: center; gap: 6px;">
                <div style="width: 10px; height: 10px; background: {COLORS['Middle']}; border-radius: 3px;"></div>
                <span style="font-size: 0.8rem; color: {COLORS['Text']};"><b>Middle:</b> Average revenue days</span>
            </div>
            <div style="display: flex; align-items: center; gap: 6px;">
                <div style="width: 10px; height: 10px; background: {COLORS['Min']}; border-radius: 3px;"></div>
                <span style="font-size: 0.8rem; color: {COLORS['Text']};"><b>Min:</b> Bottom 20% lowest revenue days</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"""
        <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.3);
                    border-radius: 8px; padding: 0.75rem;">
            <div style="font-size: 0.7rem; font-weight: 600; color: {COLORS['Max']}; margin-bottom: 0.5rem;
                 text-transform: uppercase;">Top 3 Highest Revenue Days</div>
        </div>
        """, unsafe_allow_html=True)
        for _, row in top_days.iterrows():
            st.markdown(f"""
            <div style="padding: 0.5rem 0; border-bottom: 1px solid {COLORS['Border']};">
                <span style="font-weight: 600; color: {COLORS['Text']};">{row['period']}</span>
                <span style="color: {COLORS['TextLight']}; font-size: 0.8rem;"> ({row['platform']})</span><br>
                <span style="color: {COLORS['Max']}; font-weight: 500;">{row['revenue']:,.0f}</span>
                <span style="color: {COLORS['TextMuted']}; font-size: 0.75rem;"> | {row['orders']:,} orders</span>
            </div>
            """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style="background: rgba(249, 115, 22, 0.08); border: 1px solid rgba(249, 115, 22, 0.3);
                    border-radius: 8px; padding: 0.75rem;">
            <div style="font-size: 0.7rem; font-weight: 600; color: {COLORS['Min']}; margin-bottom: 0.5rem;
                 text-transform: uppercase;">Dates with Abnormally Low Revenue</div>
        </div>
        """, unsafe_allow_html=True)
        for _, row in low_days.iterrows():
            st.markdown(f"""
            <div style="padding: 0.5rem 0; border-bottom: 1px solid {COLORS['Border']};">
                <span style="font-weight: 600; color: {COLORS['Text']};">{row['period']}</span>
                <span style="color: {COLORS['TextLight']}; font-size: 0.8rem;"> ({row['platform']})</span><br>
                <span style="color: {COLORS['Min']}; font-weight: 500;">{row['revenue']:,.0f}</span>
                <span style="color: {COLORS['TextMuted']}; font-size: 0.75rem;"> | {row['orders']:,} orders</span>
            </div>
            """, unsafe_allow_html=True)


def calculate_revenue_segments(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate revenue segments."""
    if df.empty:
        return df

    df = df.copy()

    for platform in df['platform'].unique():
        mask = df['platform'] == platform
        data = df.loc[mask, 'revenue']

        if len(data) >= 5:
            top = data.quantile(0.80)
            bottom = data.quantile(0.20)
            df.loc[mask, 'revenue_segment'] = data.apply(
                lambda x: 'Max' if x > top else ('Min' if x < bottom else 'Middle')
            )
        else:
            df.loc[mask, 'revenue_segment'] = 'Middle'

    return df
