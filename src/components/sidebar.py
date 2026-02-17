"""
Sidebar component for DPLUS Dashboard.
Light skincare theme styling.
"""

import streamlit as st
from datetime import date, timedelta
from typing import Dict
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import COLORS
from data.time_utils import get_comparison_period, format_period_label


def render_sidebar(min_date: date, max_date: date) -> Dict:
    """Render the sidebar with filters."""

    # Sidebar header - Soft UI style
    st.sidebar.markdown(f"""
    <div style="padding: 1.5rem 0.5rem 1rem; text-align: center; margin-bottom: 0.5rem;">
        <div style="font-size: 1.5rem; font-weight: 700; color: {COLORS['Primary']};">
            D Plus Skin
        </div>
        <div style="font-size: 0.75rem; color: {COLORS['TextLight']}; margin-top: 4px; font-weight: 500; letter-spacing: 0.5px;">
            Analytics Dashboard
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown("""
    <div style="height: 1px; background: linear-gradient(90deg, transparent, #E2E8F0, transparent); margin: 0.5rem 0 1rem;"></div>
    """, unsafe_allow_html=True)

    # ==========================================================================
    # Quarter Quick Select Buttons
    # ==========================================================================
    st.sidebar.markdown(f"""
    <div style="font-size: 0.7rem; font-weight: 700; color: {COLORS['TextSection']};
         text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 0.5rem; padding-left: 0.25rem;">
        QUICK SELECT
    </div>
    """, unsafe_allow_html=True)

    # Get current year for quarters
    current_year = max_date.year

    def get_quarter_range(quarter: int, year: int) -> tuple:
        """Get start and end date for a quarter."""
        if quarter == 1:
            return date(year, 1, 1), date(year, 3, 31)
        elif quarter == 2:
            return date(year, 4, 1), date(year, 6, 30)
        elif quarter == 3:
            return date(year, 7, 1), date(year, 9, 30)
        elif quarter == 4:
            return date(year, 10, 1), date(year, 12, 31)
        return None, None

    # Quarter buttons in 2x2 grid
    q_col1, q_col2 = st.sidebar.columns(2)

    with q_col1:
        if st.button("Q1", key="q1_btn"):
            q_start, q_end = get_quarter_range(1, current_year)
            if q_start and q_end:
                st.session_state.start_date = max(q_start, min_date)
                st.session_state.end_date = min(q_end, max_date)
                st.session_state.date_preset = 'Q1'
                st.rerun()
        if st.button("Q3", key="q3_btn"):
            q_start, q_end = get_quarter_range(3, current_year)
            if q_start and q_end:
                st.session_state.start_date = max(q_start, min_date)
                st.session_state.end_date = min(q_end, max_date)
                st.session_state.date_preset = 'Q3'
                st.rerun()

    with q_col2:
        if st.button("Q2", key="q2_btn"):
            q_start, q_end = get_quarter_range(2, current_year)
            if q_start and q_end:
                st.session_state.start_date = max(q_start, min_date)
                st.session_state.end_date = min(q_end, max_date)
                st.session_state.date_preset = 'Q2'
                st.rerun()
        if st.button("Q4", key="q4_btn"):
            q_start, q_end = get_quarter_range(4, current_year)
            if q_start and q_end:
                st.session_state.start_date = max(q_start, min_date)
                st.session_state.end_date = min(q_end, max_date)
                st.session_state.date_preset = 'Q4'
                st.rerun()

    st.sidebar.markdown("""
    <div style="height: 1px; background: linear-gradient(90deg, transparent, #E2E8F0, transparent); margin: 0.75rem 0;"></div>
    """, unsafe_allow_html=True)

    # ==========================================================================
    # Quick Date Selection
    # ==========================================================================
    st.sidebar.markdown(f"""
    <div style="font-size: 0.7rem; font-weight: 700; color: {COLORS['TextSection']};
         text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 0.75rem; padding-left: 0.25rem;">
        DATE RANGE
    </div>
    """, unsafe_allow_html=True)

    quick_options = {
        'Last 7 Days': (max_date - timedelta(days=6), max_date),
        'Last 14 Days': (max_date - timedelta(days=13), max_date),
        'Last 30 Days': (max_date - timedelta(days=29), max_date),
        'Last 90 Days': (max_date - timedelta(days=89), max_date),
        'This Month': (max_date.replace(day=1), max_date),
        'Last Month': (get_last_month_start(max_date), get_last_month_end(max_date)),
        'This Year': (date(max_date.year, 1, 1), max_date),
        'All Time': (min_date, max_date),
        'Custom Range': None,
    }

    if 'date_preset' not in st.session_state:
        st.session_state.date_preset = 'Last 30 Days'
        st.session_state.start_date = max_date - timedelta(days=29)
        st.session_state.end_date = max_date

    selected_preset = st.sidebar.selectbox(
        "Select Period",
        options=list(quick_options.keys()),
        index=list(quick_options.keys()).index(st.session_state.date_preset)
        if st.session_state.date_preset in quick_options else 0,
        key='date_preset_select',
        label_visibility="collapsed"
    )

    if selected_preset != st.session_state.date_preset:
        st.session_state.date_preset = selected_preset
        if quick_options[selected_preset] is not None:
            st.session_state.start_date, st.session_state.end_date = quick_options[selected_preset]
        st.rerun()

    if selected_preset == 'Custom Range':
        col1, col2 = st.sidebar.columns(2)
        with col1:
            new_start = st.date_input(
                "Start",
                value=st.session_state.start_date,
                min_value=min_date,
                max_value=max_date,
                key='custom_start',
                label_visibility="collapsed"
            )
        with col2:
            new_end = st.date_input(
                "End",
                value=st.session_state.end_date,
                min_value=min_date,
                max_value=max_date,
                key='custom_end',
                label_visibility="collapsed"
            )

        if new_start != st.session_state.start_date or new_end != st.session_state.end_date:
            st.session_state.start_date = new_start
            st.session_state.end_date = new_end
    else:
        if quick_options[selected_preset] is not None:
            st.session_state.start_date, st.session_state.end_date = quick_options[selected_preset]

    start_date = st.session_state.start_date
    end_date = st.session_state.end_date

    # Show selected period
    st.sidebar.caption(f"{format_period_label(start_date, end_date)}")

    st.sidebar.markdown("""
    <div style="height: 1px; background: linear-gradient(90deg, transparent, #E2E8F0, transparent); margin: 1rem 0;"></div>
    """, unsafe_allow_html=True)

    # ==========================================================================
    # Comparison Mode
    # ==========================================================================
    st.sidebar.markdown(f"""
    <div style="font-size: 0.7rem; font-weight: 700; color: {COLORS['TextSection']};
         text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 0.75rem; padding-left: 0.25rem;">
        COMPARE TO
    </div>
    """, unsafe_allow_html=True)

    comparison_options = {
        'No Comparison': 'none',
        'Previous Period': 'previous_period',
        'Same Period Last Year': 'previous_year'
    }

    comparison_label = st.sidebar.selectbox(
        "Comparison",
        options=list(comparison_options.keys()),
        index=0,
        key='comparison_select',
        label_visibility="collapsed"
    )

    comparison_mode = comparison_options[comparison_label]

    compare_start, compare_end = get_comparison_period(start_date, end_date, comparison_mode)

    if compare_start and compare_end:
        compare_start = max(compare_start, min_date)
        compare_end = min(compare_end, max_date)
        st.sidebar.caption(f"vs {format_period_label(compare_start, compare_end)}")

    st.sidebar.markdown("""
    <div style="height: 1px; background: linear-gradient(90deg, transparent, #E2E8F0, transparent); margin: 1rem 0;"></div>
    """, unsafe_allow_html=True)

    # ==========================================================================
    # Granularity
    # ==========================================================================
    st.sidebar.markdown(f"""
    <div style="font-size: 0.7rem; font-weight: 700; color: {COLORS['TextSection']};
         text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 0.75rem; padding-left: 0.25rem;">
        GROUP BY
    </div>
    """, unsafe_allow_html=True)

    granularity_options = {'Day': 'D', 'Week': 'W', 'Month': 'M'}

    granularity_label = st.sidebar.radio(
        "Granularity",
        options=list(granularity_options.keys()),
        index=0,
        horizontal=True,
        key='granularity_radio',
        label_visibility="collapsed"
    )

    granularity = granularity_options[granularity_label]

    st.sidebar.markdown("""
    <div style="height: 1px; background: linear-gradient(90deg, transparent, #E2E8F0, transparent); margin: 1rem 0;"></div>
    """, unsafe_allow_html=True)

    # ==========================================================================
    # Platform Filter
    # ==========================================================================
    st.sidebar.markdown(f"""
    <div style="font-size: 0.7rem; font-weight: 700; color: {COLORS['TextSection']};
         text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 0.75rem; padding-left: 0.25rem;">
        PLATFORM
    </div>
    """, unsafe_allow_html=True)

    platform = st.sidebar.radio(
        "Platform",
        options=['All', 'TikTok', 'Shopee'],
        index=0,
        horizontal=True,
        key='platform_radio',
        label_visibility="collapsed"
    )

    st.sidebar.markdown("""
    <div style="height: 1px; background: linear-gradient(90deg, transparent, #E2E8F0, transparent); margin: 1rem 0;"></div>
    """, unsafe_allow_html=True)

    # ==========================================================================
    # Legend
    # ==========================================================================
    st.sidebar.markdown(f"""
    <div style="font-size: 0.7rem; font-weight: 700; color: {COLORS['TextSection']};
         text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 0.75rem; padding-left: 0.25rem;">
        LEGEND
    </div>
    <div style="display: flex; flex-direction: column; gap: 12px; padding: 0 0.25rem;">
        <div style="display: flex; align-items: center; gap: 12px;">
            <div style="width: 16px; height: 16px; background: {COLORS['Max']};
                 border-radius: 6px; box-shadow: 0 2px 4px rgba(16, 185, 129, 0.3);"></div>
            <span style="font-size: 0.85rem; color: {COLORS['Text']}; font-weight: 500;">Hero (High Performer)</span>
        </div>
        <div style="display: flex; align-items: center; gap: 12px;">
            <div style="width: 16px; height: 16px; background: {COLORS['Middle']};
                 border-radius: 6px; box-shadow: 0 2px 4px rgba(99, 102, 241, 0.3);"></div>
            <span style="font-size: 0.85rem; color: {COLORS['Text']}; font-weight: 500;">Core (Average)</span>
        </div>
        <div style="display: flex; align-items: center; gap: 12px;">
            <div style="width: 16px; height: 16px; background: {COLORS['Min']};
                 border-radius: 6px; box-shadow: 0 2px 4px rgba(249, 115, 22, 0.3);"></div>
            <span style="font-size: 0.85rem; color: {COLORS['Text']}; font-weight: 500;">Volume (Low Margin)</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    return {
        'start_date': start_date,
        'end_date': end_date,
        'compare_start': compare_start,
        'compare_end': compare_end,
        'comparison_mode': comparison_mode,
        'granularity': granularity,
        'platform': platform
    }


def get_last_month_start(d: date) -> date:
    """Get first day of previous month."""
    first_of_month = d.replace(day=1)
    last_of_prev = first_of_month - timedelta(days=1)
    return last_of_prev.replace(day=1)


def get_last_month_end(d: date) -> date:
    """Get last day of previous month."""
    first_of_month = d.replace(day=1)
    return first_of_month - timedelta(days=1)
