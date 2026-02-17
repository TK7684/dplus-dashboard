"""
Product Matrix chart component.
"""

import plotly.express as px
import pandas as pd
import streamlit as st
from typing import Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import COLORS
from data.time_utils import calculate_change


def render_product_matrix(
    current_data: pd.DataFrame,
    previous_data: Optional[pd.DataFrame] = None,
    show_comparison: bool = False
):
    """Render the product matrix scatter plot with Soft UI style."""

    if current_data.empty:
        st.info("No product data available.")
        return

    current_data = calculate_product_segments(current_data)
    display_data = current_data.nlargest(50, 'revenue')

    color_map = {
        'Max (Hero)': COLORS['Max'],
        'Middle (Core)': COLORS['Middle'],
        'Min (Volume)': COLORS['Min']
    }

    fig = px.scatter(
        display_data,
        x='quantity',
        y='revenue',
        color='matrix_segment',
        color_discrete_map=color_map,
        hover_name='product_name',
        hover_data={'quantity': ':,', 'revenue': ':,.0f', 'orders': ':,', 'platform': True, 'matrix_segment': False},
        labels={'quantity': 'Quantity', 'revenue': 'Revenue', 'matrix_segment': 'Segment'},
        category_orders={'matrix_segment': ['Max (Hero)', 'Middle (Core)', 'Min (Volume)']}
    )

    fig.update_traces(marker=dict(size=12, opacity=0.75, line=dict(width=2, color='white')))

    # Reference lines
    qty_med = display_data['quantity'].median()
    rev_med = display_data['revenue'].median()

    fig.add_hline(y=rev_med, line_dash="dot", line_color=COLORS['Border'], opacity=0.7, line_width=1.5)
    fig.add_vline(x=qty_med, line_dash="dot", line_color=COLORS['Border'], opacity=0.7, line_width=1.5)

    # Quadrant labels
    max_q = display_data['quantity'].max()
    max_r = display_data['revenue'].max()

    fig.add_annotation(
        x=max_q * 0.85, y=max_r * 0.92,
        text="HERO",
        showarrow=False,
        font=dict(size=11, color=COLORS['Max'], family='Inter'),
        bgcolor='rgba(255,255,255,0.8)',
        bordercolor=COLORS['Max'],
        borderwidth=1,
        opacity=0.9
    )
    fig.add_annotation(
        x=max_q * 0.85, y=max_r * 0.08,
        text="VOLUME",
        showarrow=False,
        font=dict(size=11, color=COLORS['Min'], family='Inter'),
        bgcolor='rgba(255,255,255,0.8)',
        bordercolor=COLORS['Min'],
        borderwidth=1,
        opacity=0.9
    )

    fig.update_layout(
        height=350,
        margin=dict(l=10, r=10, t=10, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode='closest',
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

    # Summary with modern metric cards
    hero = len(current_data[current_data['matrix_segment'] == 'Max (Hero)'])
    core = len(current_data[current_data['matrix_segment'] == 'Middle (Core)'])
    volume = len(current_data[current_data['matrix_segment'] == 'Min (Volume)'])

    col1, col2, col3 = st.columns(3)

    with col1:
        if show_comparison and previous_data is not None and not previous_data.empty:
            prev_data = calculate_product_segments(previous_data)
            prev_hero = len(prev_data[prev_data['matrix_segment'] == 'Max (Hero)'])
            change = calculate_change(hero, prev_hero)
            st.metric("Hero Products", f"{hero}", delta=f"{change['percentage']:+.1f}%")
        else:
            st.metric("Hero Products", f"{hero}")

    with col2:
        st.metric("Core Products", f"{core}")

    with col3:
        st.metric("Volume Drivers", f"{volume}")

    # Product Matrix Insights
    st.markdown("---")
    render_product_matrix_insights(current_data)


def render_product_matrix_insights(df: pd.DataFrame):
    """Render product matrix segment breakdown."""
    if df.empty:
        return

    # Get top 3 products from each segment
    hero_products = df[df['matrix_segment'] == 'Max (Hero)'].nlargest(3, 'revenue')[['product_name', 'platform', 'revenue', 'quantity']].copy()
    core_products = df[df['matrix_segment'] == 'Middle (Core)'].nlargest(3, 'revenue')[['product_name', 'platform', 'revenue', 'quantity']].copy()
    volume_products = df[df['matrix_segment'] == 'Min (Volume)'].nlargest(3, 'quantity')[['product_name', 'platform', 'revenue', 'quantity']].copy()

    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(74, 124, 111, 0.05) 0%, rgba(96, 165, 250, 0.05) 100%);
                border: 1px solid {COLORS['Border']}; border-radius: 12px; padding: 1rem; margin-top: 0.5rem;">
        <div style="font-size: 0.75rem; font-weight: 600; color: {COLORS['TextSection']}; margin-bottom: 0.75rem;
             text-transform: uppercase; letter-spacing: 0.5px;">Segment Definitions</div>
        <div style="display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 0.5rem;">
            <div style="display: flex; align-items: center; gap: 6px;">
                <div style="width: 10px; height: 10px; background: {COLORS['Max']}; border-radius: 3px;"></div>
                <span style="font-size: 0.8rem; color: {COLORS['Text']};"><b>Hero:</b> High Revenue (Top 33%)</span>
            </div>
            <div style="display: flex; align-items: center; gap: 6px;">
                <div style="width: 10px; height: 10px; background: {COLORS['Middle']}; border-radius: 3px;"></div>
                <span style="font-size: 0.8rem; color: {COLORS['Text']};"><b>Core:</b> Consistent Sales</span>
            </div>
            <div style="display: flex; align-items: center; gap: 6px;">
                <div style="width: 10px; height: 10px; background: {COLORS['Min']}; border-radius: 3px;"></div>
                <span style="font-size: 0.8rem; color: {COLORS['Text']};"><b>Volume:</b> High quantity, low value</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(f"""
        <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.3);
                    border-radius: 8px; padding: 0.75rem; margin-bottom: 0.5rem;">
            <div style="font-size: 0.7rem; font-weight: 600; color: {COLORS['Max']}; text-transform: uppercase;">
                Top Hero Products
            </div>
            <div style="font-size: 0.7rem; color: {COLORS['TextMuted']}; margin-top: 0.25rem;">
                High Revenue Drivers
            </div>
        </div>
        """, unsafe_allow_html=True)
        for _, row in hero_products.iterrows():
            product_name = row['product_name'][:30] + '...' if len(str(row['product_name'])) > 30 else row['product_name']
            st.markdown(f"""
            <div style="padding: 0.4rem 0; border-bottom: 1px solid {COLORS['Border']}; font-size: 0.75rem;">
                <div style="font-weight: 500; color: {COLORS['Text']};">{product_name}</div>
                <div style="color: {COLORS['Max']}; font-weight: 500;">{row['revenue']:,.0f}</div>
                <div style="color: {COLORS['TextMuted']}; font-size: 0.7rem;">{row['quantity']:,} sold | {row['platform']}</div>
            </div>
            """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style="background: rgba(99, 102, 241, 0.08); border: 1px solid rgba(99, 102, 241, 0.3);
                    border-radius: 8px; padding: 0.75rem; margin-bottom: 0.5rem;">
            <div style="font-size: 0.7rem; font-weight: 600; color: {COLORS['Middle']}; text-transform: uppercase;">
                Top Core Products
            </div>
            <div style="font-size: 0.7rem; color: {COLORS['TextMuted']}; margin-top: 0.25rem;">
                Consistent Sellers
            </div>
        </div>
        """, unsafe_allow_html=True)
        for _, row in core_products.iterrows():
            product_name = row['product_name'][:30] + '...' if len(str(row['product_name'])) > 30 else row['product_name']
            st.markdown(f"""
            <div style="padding: 0.4rem 0; border-bottom: 1px solid {COLORS['Border']}; font-size: 0.75rem;">
                <div style="font-weight: 500; color: {COLORS['Text']};">{product_name}</div>
                <div style="color: {COLORS['Middle']}; font-weight: 500;">{row['revenue']:,.0f}</div>
                <div style="color: {COLORS['TextMuted']}; font-size: 0.7rem;">{row['quantity']:,} sold | {row['platform']}</div>
            </div>
            """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div style="background: rgba(249, 115, 22, 0.08); border: 1px solid rgba(249, 115, 22, 0.3);
                    border-radius: 8px; padding: 0.75rem; margin-bottom: 0.5rem;">
            <div style="font-size: 0.7rem; font-weight: 600; color: {COLORS['Min']}; text-transform: uppercase;">
                Top Volume Products
            </div>
            <div style="font-size: 0.7rem; color: {COLORS['TextMuted']}; margin-top: 0.25rem;">
                High Quantity, Lower Value
            </div>
        </div>
        """, unsafe_allow_html=True)
        for _, row in volume_products.iterrows():
            product_name = row['product_name'][:30] + '...' if len(str(row['product_name'])) > 30 else row['product_name']
            st.markdown(f"""
            <div style="padding: 0.4rem 0; border-bottom: 1px solid {COLORS['Border']}; font-size: 0.75rem;">
                <div style="font-weight: 500; color: {COLORS['Text']};">{product_name}</div>
                <div style="color: {COLORS['Min']}; font-weight: 500;">{row['quantity']:,} units</div>
                <div style="color: {COLORS['TextMuted']}; font-size: 0.7rem;">{row['revenue']:,.0f} | {row['platform']}</div>
            </div>
            """, unsafe_allow_html=True)


def calculate_product_segments(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate product segments."""
    if df.empty:
        return df

    df = df.copy()

    for platform in df['platform'].unique():
        mask = df['platform'] == platform
        rev_thresh = df.loc[mask, 'revenue'].quantile(0.67)
        qty_med = df.loc[mask, 'quantity'].median()

        def label(row):
            if row['revenue'] >= rev_thresh:
                return 'Max (Hero)'
            elif row['quantity'] >= qty_med and row['revenue'] < rev_thresh:
                return 'Min (Volume)'
            return 'Middle (Core)'

        df.loc[mask, 'matrix_segment'] = df.loc[mask].apply(label, axis=1)

    return df
