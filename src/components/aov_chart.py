"""
AOV Analysis chart component.
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


def render_aov_chart(
    current_data: pd.DataFrame,
    previous_data: Optional[pd.DataFrame] = None,
    show_comparison: bool = False
):
    """Render the AOV analysis chart with Soft UI style."""

    if current_data.empty:
        st.info("No AOV data available.")
        return

    current_data = calculate_aov_segments(current_data)
    max_periods = 30

    fig = go.Figure()
    platforms = current_data['platform'].unique()

    for platform in platforms:
        platform_data = current_data[current_data['platform'] == platform].copy()
        platform_data = platform_data.sort_values('period').tail(max_periods)

        colors = platform_data['aov_segment'].map({
            'Max': COLORS['Max'],
            'Middle': COLORS['Middle'],
            'Min': COLORS['Min']
        })

        fig.add_trace(go.Bar(
            x=platform_data['period'],
            y=platform_data['aov'],
            name=platform,
            marker_color=colors,
            marker_line=dict(color='white', width=1),
            opacity=0.9,
            hovertemplate='<b>%{x}</b><br>AOV: %{y:,.0f}<extra></extra>'
        ))

    avg_aov = current_data['aov'].mean()

    fig.add_hline(
        y=avg_aov,
        line_dash="dot",
        line_color=COLORS['Primary'],
        line_width=2,
        annotation_text=f"Avg: {avg_aov:,.0f}",
        annotation_position="right",
        annotation=dict(
            font=dict(color=COLORS['Primary'], size=11),
            bgcolor='rgba(255,255,255,0.9)',
            bordercolor=COLORS['Primary'],
            borderwidth=1
        )
    )

    fig.update_layout(
        barmode='group',
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

    # Summary metrics
    max_aov = current_data['aov'].max()
    min_aov = current_data['aov'].min()
    max_count = len(current_data[current_data['aov_segment'] == 'Max'])

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if show_comparison and previous_data is not None and not previous_data.empty:
            prev_data = calculate_aov_segments(previous_data)
            prev_avg = prev_data['aov'].mean()
            change = calculate_change(avg_aov, prev_avg)
            st.metric("Avg AOV", f"{avg_aov:,.0f}", delta=f"{change['percentage']:+.1f}%")
        else:
            st.metric("Avg AOV", f"{avg_aov:,.0f}")

    with col2:
        st.metric("Highest", f"{max_aov:,.0f}")

    with col3:
        st.metric("Lowest", f"{min_aov:,.0f}")

    with col4:
        st.metric("High AOV Days", f"{max_count}")

    # Insights section
    st.markdown("---")
    render_aov_insights(current_data, avg_aov)


def render_aov_insights(df: pd.DataFrame, avg_aov: float):
    """Render AOV insights with top/low performing days."""
    if df.empty:
        return

    # Get top 3 highest AOV days
    top_days = df.nlargest(3, 'aov')[['period', 'aov', 'revenue', 'orders', 'platform']].copy()
    top_days['period'] = top_days['period'].astype(str)

    # Get bottom 3 lowest AOV days
    low_days = df.nsmallest(3, 'aov')[['period', 'aov', 'revenue', 'orders', 'platform']].copy()
    low_days['period'] = low_days['period'].astype(str)

    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(74, 124, 111, 0.05) 0%, rgba(96, 165, 250, 0.05) 100%);
                border: 1px solid {COLORS['Border']}; border-radius: 12px; padding: 1rem; margin-top: 0.5rem;">
        <div style="font-size: 0.75rem; font-weight: 600; color: {COLORS['TextSection']}; margin-bottom: 0.75rem;
             text-transform: uppercase; letter-spacing: 0.5px;">Segment Definitions</div>
        <div style="display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1rem;">
            <div style="display: flex; align-items: center; gap: 6px;">
                <div style="width: 10px; height: 10px; background: {COLORS['Max']}; border-radius: 3px;"></div>
                <span style="font-size: 0.8rem; color: {COLORS['Text']};"><b>Max:</b> AOV > +20% above average ({avg_aov * 1.2:,.0f})</span>
            </div>
            <div style="display: flex; align-items: center; gap: 6px;">
                <div style="width: 10px; height: 10px; background: {COLORS['Middle']}; border-radius: 3px;"></div>
                <span style="font-size: 0.8rem; color: {COLORS['Text']};"><b>Middle:</b> Close to average</span>
            </div>
            <div style="display: flex; align-items: center; gap: 6px;">
                <div style="width: 10px; height: 10px; background: {COLORS['Min']}; border-radius: 3px;"></div>
                <span style="font-size: 0.8rem; color: {COLORS['Text']};"><b>Min:</b> AOV < -20% below average ({avg_aov * 0.8:,.0f})</span>
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
                 text-transform: uppercase;">Top 3 Highest AOV Days</div>
            <div style="font-size: 0.7rem; color: {COLORS['TextMuted']}; margin-top: 0.25rem;
                 font-style: italic;">Check for: Bundles, Livestreams, Promotions</div>
        </div>
        """, unsafe_allow_html=True)
        for _, row in top_days.iterrows():
            st.markdown(f"""
            <div style="padding: 0.5rem 0; border-bottom: 1px solid {COLORS['Border']};">
                <span style="font-weight: 600; color: {COLORS['Text']};">{row['period']}</span>
                <span style="color: {COLORS['TextLight']}; font-size: 0.8rem;"> ({row['platform']})</span><br>
                <span style="color: {COLORS['Max']}; font-weight: 500;">{row['aov']:,.0f}/order</span>
                <span style="color: {COLORS['TextMuted']}; font-size: 0.75rem;"> | {row['orders']:,} orders | {row['revenue']:,.0f} total</span>
            </div>
            """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style="background: rgba(249, 115, 22, 0.08); border: 1px solid rgba(249, 115, 22, 0.3);
                    border-radius: 8px; padding: 0.75rem;">
            <div style="font-size: 0.7rem; font-weight: 600; color: {COLORS['Min']}; margin-bottom: 0.5rem;
                 text-transform: uppercase;">Top 3 Lowest AOV Days</div>
            <div style="font-size: 0.7rem; color: {COLORS['TextMuted']}; margin-top: 0.25rem;
                 font-style: italic;">Investigate: Low-value items, single purchases</div>
        </div>
        """, unsafe_allow_html=True)
        for _, row in low_days.iterrows():
            st.markdown(f"""
            <div style="padding: 0.5rem 0; border-bottom: 1px solid {COLORS['Border']};">
                <span style="font-weight: 600; color: {COLORS['Text']};">{row['period']}</span>
                <span style="color: {COLORS['TextLight']}; font-size: 0.8rem;"> ({row['platform']})</span><br>
                <span style="color: {COLORS['Min']}; font-weight: 500;">{row['aov']:,.0f}/order</span>
                <span style="color: {COLORS['TextMuted']}; font-size: 0.75rem;"> | {row['orders']:,} orders | {row['revenue']:,.0f} total</span>
            </div>
            """, unsafe_allow_html=True)


def calculate_aov_segments(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate AOV segments."""
    if df.empty:
        return df

    df = df.copy()
    avg = df['aov'].mean()

    df['aov_segment'] = df['aov'].apply(
        lambda x: 'Max' if x > (avg * 1.2) else ('Min' if x < (avg * 0.8) else 'Middle')
    )

    return df
