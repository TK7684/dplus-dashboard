"""
Portfolio Health chart component.
"""

import plotly.graph_objects as go
import pandas as pd
import streamlit as st
from typing import Optional, Dict

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import COLORS
from data.time_utils import calculate_change
from components.product_matrix import calculate_product_segments


def render_portfolio_health(
    current_data: pd.DataFrame,
    previous_data: Optional[pd.DataFrame] = None,
    show_comparison: bool = False
):
    """Render the portfolio health visualization with Soft UI style."""

    if current_data.empty:
        st.info("No portfolio data available.")
        return

    current_data = calculate_product_segments(current_data)
    segments = calculate_segment_distribution(current_data)
    risk_level = determine_risk_level(segments)
    recommendation = get_recommendation(segments, risk_level)

    # Donut chart
    labels = ['Hero', 'Core', 'Volume']
    values = [
        segments.get('Max (Hero)', {}).get('revenue', 0),
        segments.get('Middle (Core)', {}).get('revenue', 0),
        segments.get('Min (Volume)', {}).get('revenue', 0)
    ]
    colors = [COLORS['Max'], COLORS['Middle'], COLORS['Min']]

    non_zero = [(label, val, col) for label, val, col in zip(labels, values, colors) if val > 0]

    if not non_zero:
        st.info("No revenue data.")
        return

    labels_f, values_f, colors_f = zip(*non_zero)
    total_revenue = sum(values)

    fig = go.Figure()

    fig.add_trace(go.Pie(
        labels=labels_f,
        values=values_f,
        hole=0.65,
        marker_colors=colors_f,
        textinfo='percent',
        textposition='outside',
        textfont=dict(size=12, color=COLORS['Text']),
        hovertemplate='<b>%{label}</b><br>Revenue: %{value:,.0f}<br>Share: %{percent}<extra></extra>',
        marker=dict(line=dict(color='white', width=2))
    ))

    fig.add_annotation(
        text=f'<b>{total_revenue:,.0f}</b>',
        x=0.5, y=0.55,
        font=dict(size=16, color=COLORS['Text']),
        showarrow=False
    )
    fig.add_annotation(
        text='Total Revenue',
        x=0.5, y=0.4,
        font=dict(size=11, color=COLORS['TextMuted']),
        showarrow=False
    )

    fig.update_layout(
        height=280,
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color=COLORS['Text'])
    )

    col1, col2 = st.columns([1, 1.5])

    with col1:
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Risk level with Soft UI styling
        risk_colors = {'Low': COLORS['Max'], 'Medium': '#F59E0B', 'High': COLORS['Min']}
        risk_color = risk_colors.get(risk_level, COLORS['Middle'])

        st.markdown(f"""
        <div style="margin-bottom: 16px; padding: 12px 16px; background: linear-gradient(135deg, rgba(255,255,255,0.9) 0%, rgba(248,250,252,0.9) 100%); border-radius: 12px; border: 1px solid {COLORS['Border']};">
            <span style="font-size: 11px; color: {COLORS['TextMuted']}; text-transform: uppercase; letter-spacing: 0.5px;">Risk Level</span><br>
            <span style="font-size: 20px; font-weight: 700; color: {risk_color};">{risk_level}</span>
        </div>
        """, unsafe_allow_html=True)

        # Segment breakdown with modern styling
        st.markdown(f"""
        <div style="font-size: 12px; font-weight: 600; color: {COLORS['Text']}; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.5px;">
            Revenue Split
        </div>
        """, unsafe_allow_html=True)

        for seg, label in [('Max (Hero)', 'Hero'), ('Middle (Core)', 'Core'), ('Min (Volume)', 'Volume')]:
            data = segments.get(seg, {'revenue': 0, 'percentage': 0})
            color = {'Hero': COLORS['Max'], 'Core': COLORS['Middle'], 'Volume': COLORS['Min']}[label]

            pct = data['percentage']
            delta_str = ""

            if show_comparison and previous_data is not None and not previous_data.empty:
                prev_seg = calculate_segment_distribution(calculate_product_segments(previous_data))
                prev_pct = prev_seg.get(seg, {}).get('percentage', 0)
                change = calculate_change(pct, prev_pct)
                if change['status'] != 'no_change':
                    arrow = '+' if change['percentage'] > 0 else ''
                    delta_str = f" <span style='font-size: 10px; color: {color}; font-weight: 500;'>({arrow}{change['percentage']:.1f}%)</span>"

            st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px; padding: 8px 12px; background: rgba(255,255,255,0.7); border-radius: 8px; border: 1px solid {COLORS['Border']};">
                <div style="width: 12px; height: 12px; background: {color}; border-radius: 4px; box-shadow: 0 2px 4px {color}40;"></div>
                <span style="font-size: 13px; color: {COLORS['Text']};"><b>{label}</b>: {data['revenue']:,.0f} ({pct:.1f}%){delta_str}</span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("")
        st.info(f"{recommendation}")


def calculate_segment_distribution(df: pd.DataFrame) -> Dict:
    """Calculate revenue distribution by segment."""
    if df.empty:
        return {}

    segment_rev = df.groupby('matrix_segment')['revenue'].sum()
    total = segment_rev.sum()

    if total == 0:
        return {}

    segments = {}
    for seg in ['Max (Hero)', 'Middle (Core)', 'Min (Volume)']:
        rev = segment_rev.get(seg, 0)
        segments[seg] = {'revenue': rev, 'percentage': (rev / total) * 100}

    return segments


def determine_risk_level(segments: Dict) -> str:
    """Determine portfolio risk level."""
    if not segments:
        return 'Unknown'

    hero_pct = segments.get('Max (Hero)', {}).get('percentage', 0)
    core_pct = segments.get('Middle (Core)', {}).get('percentage', 0)

    if hero_pct > 60:
        return 'High'
    elif core_pct < 25:
        return 'Medium'
    return 'Low'


def get_recommendation(segments: Dict, risk_level: str) -> str:
    """Get recommendation."""
    if risk_level == 'High':
        return 'High reliance on Hero products. Promote Core products.'
    elif risk_level == 'Medium':
        return 'Core segment weak. Opportunity to grow mid-tier.'
    return 'Portfolio is well-balanced.'


def render_segment_breakdown(
    current_data: pd.DataFrame,
    previous_data: Optional[pd.DataFrame] = None,
    show_comparison: bool = False
):
    """Render detailed product breakdown."""
    if current_data.empty:
        return

    current_data = calculate_product_segments(current_data)

    st.markdown("### Top Products by Segment")

    tab1, tab2, tab3 = st.tabs(["Hero Products", "Core Products", "Volume Drivers"])

    for tab, segment in [(tab1, 'Max (Hero)'), (tab2, 'Middle (Core)'), (tab3, 'Min (Volume)')]:
        with tab:
            products = current_data[current_data['matrix_segment'] == segment].nlargest(15, 'revenue')

            if products.empty:
                st.write(f"No {segment.split(' ')[1].lower()} products.")
            else:
                display_df = products[['product_name', 'platform', 'revenue', 'quantity', 'orders']].copy()
                display_df['revenue'] = display_df['revenue'].apply(lambda x: f"{x:,.0f}")
                display_df.columns = ['Product', 'Platform', 'Revenue', 'Qty', 'Orders']

                st.dataframe(display_df, use_container_width=True, hide_index=True)
