"""
DPLUS Dashboard - Main Application
Light, fresh theme for skincare & wellness analytics.
With auto-refresh monitoring for new data files.
"""

import streamlit as st
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import COLORS
from data.database import (
    build_database,
    refresh_database,
    get_new_files_count,
    query_revenue_by_period,
    query_aov_by_period,
    query_product_stats,
    query_summary_metrics,
    query_date_range,
    get_db_stats
)
from data.time_utils import format_period_label, calculate_change
from components.sidebar import render_sidebar
from components.revenue_chart import render_revenue_chart, calculate_revenue_segments
from components.aov_chart import render_aov_chart
from components.product_matrix import render_product_matrix
from components.portfolio_health import render_portfolio_health, render_segment_breakdown


def setup_page():
    """Configure page settings with Soft UI Evolution theme."""
    st.set_page_config(
        page_title="D Plus Skin Analytics",
        page_icon="✨",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Soft UI Evolution Theme CSS
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Fira+Code:wght@400;500&display=swap');

        /* ========================================
           CSS Variables
           ======================================== */
        :root {{
            --primary: {COLORS['Primary']};
            --secondary: {COLORS['Secondary']};
            --accent: {COLORS['Accent']};
            --background: {COLORS['Background']};
            --card: {COLORS['Card']};
            --card-hover: {COLORS['CardHover']};
            --border: {COLORS['Border']};
            --text: {COLORS['Text']};
            --text-light: {COLORS['TextLight']};
            --text-muted: {COLORS['TextMuted']};
            --shadow-light: {COLORS['ShadowLight']};
            --shadow-medium: {COLORS['ShadowMedium']};
            --shadow-dark: {COLORS['ShadowDark']};
            --radius-sm: 8px;
            --radius-md: 12px;
            --radius-lg: 16px;
            --radius-xl: 24px;
            --transition-fast: 150ms ease;
            --transition-normal: 250ms ease;
            --transition-slow: 350ms ease;
        }}

        /* ========================================
           Base Styles
           ======================================== */
        * {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }}

        .stApp {{
            background: var(--background);
        }}

        .main .block-container {{
            padding-top: 2rem;
            padding-bottom: 2rem;
            max-width: 1440px;
        }}

        /* ========================================
           Sidebar - Soft Glass Effect
           ======================================== */
        section[data-testid="stSidebar"] {{
            background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 50%, #F1F5F9 100%);
            border-right: 1px solid var(--border);
            box-shadow: 4px 0 24px var(--shadow-light);
        }}

        section[data-testid="stSidebar"] > div {{
            padding-top: 1rem;
        }}

        section[data-testid="stSidebar"] .element-container {{
            margin-bottom: 0.5rem;
        }}

        /* Sidebar text colors - force dark text */
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] span,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] div,
        section[data-testid="stSidebar"] .stMarkdown {{
            color: {COLORS['Text']} !important;
        }}

        section[data-testid="stSidebar"] .stSelectbox label,
        section[data-testid="stSidebar"] .stRadio label {{
            color: {COLORS['Text']} !important;
        }}

        section[data-testid="stSidebar"] .stCaption {{
            color: {COLORS['TextLight']} !important;
        }}

        /* ========================================
           Headers & Typography
           ======================================== */
        h1 {{
            color: var(--text);
            font-weight: 700;
            font-size: 2rem;
            letter-spacing: -0.02em;
            margin-bottom: 0.25rem;
            background: linear-gradient(135deg, var(--text) 0%, var(--primary) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}

        .dashboard-subtitle {{
            color: var(--text-light);
            font-size: 0.95rem;
            font-weight: 400;
            margin-bottom: 1.5rem;
        }}

        .section-header {{
            font-size: 0.875rem;
            font-weight: 600;
            color: var(--text);
            padding: 0.75rem 1rem;
            background: linear-gradient(135deg, var(--primary) 0%, #5A9A8F 100%);
            color: white;
            border-radius: var(--radius-md);
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            box-shadow: 0 4px 12px rgba(74, 124, 111, 0.25);
        }}

        .section-header::before {{
            content: '';
            width: 4px;
            height: 16px;
            background: white;
            border-radius: 2px;
        }}

        /* ========================================
           Cards - Soft UI Style
           ======================================== */
        .card {{
            background: var(--card);
            border-radius: var(--radius-lg);
            border: 1px solid var(--border);
            box-shadow: 0 4px 16px var(--shadow-light), 0 1px 3px var(--shadow-light);
            padding: 1.5rem;
            transition: all var(--transition-normal);
        }}

        .card:hover {{
            box-shadow: 0 8px 24px var(--shadow-medium), 0 2px 6px var(--shadow-light);
            transform: translateY(-2px);
        }}

        /* ========================================
           Metrics - Compact Style
           ======================================== */
        [data-testid="stMetric"] {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 0.75rem 1rem;
            box-shadow: 0 2px 8px var(--shadow-light);
            transition: all var(--transition-fast);
        }}

        [data-testid="stMetric"]:hover {{
            box-shadow: 0 4px 12px var(--shadow-medium);
        }}

        [data-testid="stMetricValue"] {{
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text);
            letter-spacing: -0.01em;
            font-family: 'Inter', sans-serif;
            line-height: 1.2;
        }}

        [data-testid="stMetricLabel"] {{
            font-size: 0.7rem;
            font-weight: 600;
            color: var(--text-light);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 0.25rem;
        }}

        [data-testid="stMetricDelta"] {{
            font-size: 0.8rem;
            font-weight: 500;
        }}

        [data-testid="stMetricDelta"] > svg {{
            fill: var(--accent);
        }}

        /* Positive delta - Green */
        [data-testid="stMetricDelta"][aria-label*="↑"],
        [data-testid="stMetricDelta"]:has(svg[aria-label*="up"]) {{
            color: #10B981;
        }}

        /* Negative delta - Orange */
        [data-testid="stMetricDelta"][aria-label*="↓"],
        [data-testid="stMetricDelta"]:has(svg[aria-label*="down"]) {{
            color: #F97316;
        }}

        /* ========================================
           Info Banner - Gradient Style
           ======================================== */
        .info-banner {{
            background: linear-gradient(135deg, rgba(74, 124, 111, 0.08) 0%, rgba(96, 165, 250, 0.08) 100%);
            border: 1px solid rgba(74, 124, 111, 0.2);
            border-left: 4px solid var(--primary);
            padding: 1rem 1.25rem;
            border-radius: 0 var(--radius-md) var(--radius-md) 0;
            margin-bottom: 1.5rem;
            backdrop-filter: blur(8px);
        }}

        .info-banner span {{
            font-size: 0.875rem;
        }}

        /* ========================================
           Form Controls - Soft Style
           ======================================== */
        .stSelectbox > div > div {{
            border-radius: var(--radius-sm);
            border: 1px solid var(--border);
            background: var(--card);
            box-shadow: 0 1px 3px var(--shadow-light);
            transition: all var(--transition-fast);
        }}

        .stSelectbox > div > div:hover {{
            border-color: var(--primary);
            box-shadow: 0 2px 6px var(--shadow-medium);
        }}

        .stSelectbox > div > div:focus-within {{
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(74, 124, 111, 0.15);
        }}

        .stRadio > div {{
            gap: 0.75rem;
            flex-wrap: wrap;
        }}

        .stRadio > div > label {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            padding: 0.5rem 1rem;
            transition: all var(--transition-fast);
            cursor: pointer;
        }}

        .stRadio > div > label:hover {{
            background: var(--card-hover);
            border-color: var(--primary);
        }}

        .stRadio > div > label[data-checked="true"] {{
            background: var(--primary);
            border-color: var(--primary);
            color: white;
        }}

        /* ========================================
           Buttons - Elevated Style
           ======================================== */
        .stButton > button {{
            border-radius: var(--radius-sm);
            border: 1px solid var(--border);
            background: var(--card);
            box-shadow: 0 2px 4px var(--shadow-light);
            transition: all var(--transition-fast);
            font-weight: 600;
            font-size: 0.85rem;
            padding: 0.5rem 1rem;
            color: var(--text);
        }}

        .stButton > button:hover {{
            background: var(--primary);
            border-color: var(--primary);
            color: white;
            box-shadow: 0 4px 8px var(--shadow-medium);
        }}

        .stButton > button:active {{
            transform: translateY(0);
            box-shadow: 0 1px 2px var(--shadow-light);
        }}

        .stButton > button[kind="primary"] {{
            background: var(--primary);
            color: white;
        }}

        /* ========================================
           Expander - Accordion Style
           ======================================== */
        .streamlit-expanderHeader {{
            background: var(--card);
            border-radius: var(--radius-md);
            border: 1px solid var(--border);
            box-shadow: 0 2px 6px var(--shadow-light);
            transition: all var(--transition-fast);
        }}

        .streamlit-expanderHeader:hover {{
            background: var(--card-hover);
            box-shadow: 0 4px 10px var(--shadow-medium);
        }}

        /* ========================================
           Dataframe - Clean Style
           ======================================== */
        .stDataFrame {{
            border-radius: var(--radius-md);
            overflow: hidden;
            border: 1px solid var(--border);
            box-shadow: 0 2px 8px var(--shadow-light);
        }}

        .stDataFrame th {{
            background: linear-gradient(180deg, #F8FAFC 0%, #F1F5F9 100%);
            font-weight: 600;
            color: var(--text);
        }}

        .stDataFrame td {{
            border-bottom: 1px solid var(--border);
        }}

        .stDataFrame tr:hover td {{
            background: rgba(74, 124, 111, 0.05);
        }}

        /* ========================================
           Tabs - Modern Pill Style
           ======================================== */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 0.5rem;
            background: transparent;
        }}

        .stTabs [data-baseweb="tab"] {{
            border-radius: var(--radius-md);
            padding: 0.75rem 1.5rem;
            background: var(--card);
            border: 1px solid var(--border);
            box-shadow: 0 2px 4px var(--shadow-light);
            transition: all var(--transition-fast);
            font-weight: 500;
        }}

        .stTabs [data-baseweb="tab"]:hover {{
            background: var(--card-hover);
            box-shadow: 0 4px 8px var(--shadow-medium);
        }}

        .stTabs [aria-selected="true"] {{
            background: linear-gradient(135deg, var(--primary) 0%, #5A9A8F 100%);
            color: white;
            border-color: transparent;
            box-shadow: 0 4px 12px rgba(74, 124, 111, 0.3);
        }}

        /* ========================================
           Charts - Plotly Overrides
           ======================================== */
        .stPlotlyChart {{
            border-radius: var(--radius-md);
            overflow: hidden;
        }}

        /* ========================================
           Captions & Small Text
           ======================================== */
        .stCaption {{
            color: var(--text-muted);
            font-size: 0.8rem;
        }}

        /* ========================================
           Dividers
           ======================================== */
        hr {{
            border: none;
            height: 1px;
            background: linear-gradient(90deg, transparent 0%, var(--border) 20%, var(--border) 80%, transparent 100%);
            margin: 2rem 0;
        }}

        /* ========================================
           Hide Default Elements
           ======================================== */
        #MainMenu {{ visibility: hidden; }}
        footer {{ visibility: hidden; }}
        header {{ height: 0 !important; }}

        /* ========================================
           Loading Spinner
           ======================================== */
        .stSpinner > div {{
            border-color: var(--primary) transparent transparent transparent;
        }}

        /* ========================================
           Info/Warning/Success Boxes
           ======================================== */
        .stAlert {{
            border-radius: var(--radius-md);
            border: 1px solid var(--border);
            box-shadow: 0 2px 6px var(--shadow-light);
        }}

        /* ========================================
           Date Input
           ======================================== */
        .stDateInput > div > div {{
            border-radius: var(--radius-sm);
            border: 1px solid var(--border);
            box-shadow: 0 1px 3px var(--shadow-light);
        }}

        .stDateInput > div > div:focus-within {{
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(74, 124, 111, 0.15);
        }}

        /* ========================================
           Responsive Adjustments
           ======================================== */
        @media (max-width: 768px) {{
            .main .block-container {{
                padding: 1rem;
            }}

            h1 {{
                font-size: 1.5rem;
            }}

            [data-testid="stMetricValue"] {{
                font-size: 1.5rem;
            }}
        }}
    </style>
    """, unsafe_allow_html=True)


def render_kpi_header(current_metrics: dict, previous_metrics: dict, show_comparison: bool):
    """Render KPI metrics at the top."""
    st.markdown('<div class="section-header">Key Metrics</div>', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)

    metrics_config = [
        ('Revenue', 'total_revenue', ''),
        ('Orders', 'total_orders', ''),
        ('Items Sold', 'total_quantity', ''),
        ('Avg Order Value', 'aov', ''),
    ]

    for (label, key, prefix), col in zip(metrics_config, [col1, col2, col3, col4]):
        with col:
            current = current_metrics.get(key) or 0
            previous = (previous_metrics.get(key) or 0) if previous_metrics else 0

            if show_comparison and previous > 0:
                change = calculate_change(current, previous)
                delta = f"{change['percentage']:+.1f}%"
                st.metric(label, f"{prefix}{current:,.0f}", delta=delta)
            else:
                st.metric(label, f"{prefix}{current:,.0f}")


def render_period_info(filters: dict):
    """Render period information banner with Soft UI style."""
    period_text = format_period_label(filters['start_date'], filters['end_date'])
    platform_text = filters['platform']
    granularity_text = {'D': 'Daily', 'W': 'Weekly', 'M': 'Monthly', 'Q': 'Quarterly'}.get(
        filters['granularity'], 'Daily'
    )

    st.markdown(f"""
    <div class="info-banner">
        <span style="font-weight: 600; color: var(--primary);">Period</span>
        <span style="color: var(--text); margin-left: 6px;">{period_text}</span>
        <span style="margin: 0 12px; color: var(--border);">|</span>
        <span style="font-weight: 600; color: var(--primary);">Platform</span>
        <span style="color: var(--text); margin-left: 6px;">{platform_text}</span>
        <span style="margin: 0 12px; color: var(--border);">|</span>
        <span style="font-weight: 600; color: var(--primary);">View</span>
        <span style="color: var(--text); margin-left: 6px;">{granularity_text}</span>
    </div>
    """, unsafe_allow_html=True)


def main():
    """Main application."""
    setup_page()

    # Initialize session state for refresh
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = time.time()
    if 'auto_refresh' not in st.session_state:
        st.session_state.auto_refresh = True

    # Build/refresh database
    with st.spinner("Loading..."):
        build_database(show_progress=True)

    # Check for new files and show refresh button if needed
    new_files = get_new_files_count()

    # Header with refresh controls
    col_title, col_refresh = st.columns([4, 1])

    with col_title:
        st.title("D Plus Skin Analytics")
        st.markdown('<p class="dashboard-subtitle">Skincare & Wellness Performance Dashboard</p>', unsafe_allow_html=True)

    with col_refresh:
        # Refresh button
        if st.button("Refresh Data", key="refresh_btn", width="stretch"):
            with st.spinner("Refreshing..."):
                rows = refresh_database()
                if rows > 0:
                    st.success(f"Loaded {rows:,} new records!")
                    st.rerun()
                else:
                    st.info("No new data found")

        # Auto-refresh toggle
        auto_refresh = st.checkbox("Auto-refresh", value=st.session_state.auto_refresh, key="auto_refresh_check")
        st.session_state.auto_refresh = auto_refresh

    # Show new files indicator
    if new_files > 0:
        st.info(f" {new_files} new file(s) detected. Click 'Refresh Data' to load.")

    min_date, max_date = query_date_range()
    filters = render_sidebar(min_date, max_date)

    start_date = filters['start_date']
    end_date = filters['end_date']
    compare_start = filters['compare_start']
    compare_end = filters['compare_end']
    granularity = filters['granularity']
    platform = filters['platform']
    comparison_mode = filters['comparison_mode']

    show_comparison = comparison_mode != 'none' and compare_start and compare_end

    # Query data
    with st.spinner(""):
        revenue_data = query_revenue_by_period(start_date, end_date, granularity, platform)
        aov_data = query_aov_by_period(start_date, end_date, granularity, platform)
        product_data = query_product_stats(start_date, end_date, platform)
        current_metrics = query_summary_metrics(start_date, end_date, platform)
        revenue_data = calculate_revenue_segments(revenue_data)

    if show_comparison:
        prev_revenue = query_revenue_by_period(compare_start, compare_end, granularity, platform)
        prev_aov = query_aov_by_period(compare_start, compare_end, granularity, platform)
        prev_products = query_product_stats(compare_start, compare_end, platform)
        previous_metrics = query_summary_metrics(compare_start, compare_end, platform)
        prev_revenue = calculate_revenue_segments(prev_revenue)
    else:
        prev_revenue = None
        prev_aov = None
        prev_products = None
        previous_metrics = None

    render_period_info(filters)
    render_kpi_header(current_metrics, previous_metrics, show_comparison)

    st.markdown("---")

    # Charts Row 1
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="section-header">Revenue Trends</div>', unsafe_allow_html=True)
        render_revenue_chart(revenue_data, prev_revenue, show_comparison)

    with col2:
        st.markdown('<div class="section-header">AOV Analysis</div>', unsafe_allow_html=True)
        render_aov_chart(aov_data, prev_aov, show_comparison)

    st.markdown("---")

    # Charts Row 2
    col3, col4 = st.columns(2)

    with col3:
        st.markdown('<div class="section-header">Product Matrix</div>', unsafe_allow_html=True)
        render_product_matrix(product_data, prev_products, show_comparison)

    with col4:
        st.markdown('<div class="section-header">Portfolio Health</div>', unsafe_allow_html=True)
        render_portfolio_health(product_data, prev_products, show_comparison)

    # Product breakdown
    st.markdown("---")
    with st.expander("View Product Breakdown by Segment", expanded=False):
        render_segment_breakdown(product_data, prev_products, show_comparison)

    # Footer
    st.markdown("---")
    db_stats = get_db_stats()
    st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.5rem 0;">
        <span style="font-size: 0.8rem; color: {COLORS['TextMuted']};">
            Data: <b style="color: {COLORS['TextLight']};">{db_stats['total_rows']:,}</b> records |
            <b style="color: {COLORS['TextLight']};">{db_stats['unique_orders']:,}</b> orders
        </span>
        <span style="font-size: 0.8rem; color: {COLORS['TextMuted']};">
            Date range: <b style="color: {COLORS['TextLight']};">{min_date}</b> to <b style="color: {COLORS['TextLight']};">{max_date}</b>
        </span>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
