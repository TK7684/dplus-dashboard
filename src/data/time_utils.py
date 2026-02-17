"""
Time comparison utilities for DPLUS Dashboard.
Handles period calculations and comparisons.
"""

from datetime import date, timedelta
from typing import Tuple, Optional
import pandas as pd


def get_comparison_period(
    start_date: date,
    end_date: date,
    comparison_type: str = 'previous_period'
) -> Tuple[Optional[date], Optional[date]]:
    """
    Calculate the comparison period based on the selected date range.

    Args:
        start_date: Current period start
        end_date: Current period end
        comparison_type: Type of comparison
            - 'previous_period': Previous equivalent period
            - 'previous_year': Same period last year
            - 'none': No comparison

    Returns:
        Tuple of (compare_start, compare_end) or (None, None)
    """
    if comparison_type == 'none':
        return None, None

    period_length = (end_date - start_date).days + 1

    if comparison_type == 'previous_period':
        # Previous equivalent period
        compare_end = start_date - timedelta(days=1)
        compare_start = compare_end - timedelta(days=period_length - 1)
        return compare_start, compare_end

    elif comparison_type == 'previous_year':
        # Same period last year
        try:
            compare_start = start_date.replace(year=start_date.year - 1)
            compare_end = end_date.replace(year=end_date.year - 1)
            return compare_start, compare_end
        except ValueError:
            # Handle leap year issues
            compare_start = start_date.replace(year=start_date.year - 1, day=28)
            compare_end = end_date.replace(year=end_date.year - 1, day=28)
            return compare_start, compare_end

    elif comparison_type == 'previous_month':
        # Previous month
        first_of_month = start_date.replace(day=1)
        compare_end = first_of_month - timedelta(days=1)
        compare_start = compare_end.replace(day=1)
        return compare_start, compare_end

    elif comparison_type == 'previous_quarter':
        # Previous quarter
        quarter = (start_date.month - 1) // 3
        if quarter == 0:
            compare_year = start_date.year - 1
            compare_quarter = 3
        else:
            compare_year = start_date.year
            compare_quarter = quarter - 1

        compare_start = date(compare_year, compare_quarter * 3 + 1, 1)
        if compare_quarter == 3:
            compare_end = date(compare_year, 12, 31)
        else:
            next_quarter_start = date(compare_year, (compare_quarter + 1) * 3 + 1, 1)
            compare_end = next_quarter_start - timedelta(days=1)
        return compare_start, compare_end

    return None, None


def calculate_change(current: float, previous: float) -> dict:
    """
    Calculate change between current and previous values.

    Returns:
        Dictionary with change amount, percentage, and direction
    """
    if previous == 0 or pd.isna(previous):
        if current > 0:
            return {
                'absolute': current,
                'percentage': 100.0,
                'direction': 'up',
                'status': 'new'
            }
        return {
            'absolute': 0,
            'percentage': 0,
            'direction': 'neutral',
            'status': 'no_change'
        }

    absolute = current - previous
    percentage = ((current - previous) / previous) * 100

    if percentage > 0:
        direction = 'up'
    elif percentage < 0:
        direction = 'down'
    else:
        direction = 'neutral'

    return {
        'absolute': absolute,
        'percentage': percentage,
        'direction': direction,
        'status': 'changed'
    }


def format_comparison(current: float, previous: float, prefix: str = '', suffix: str = '') -> str:
    """Format a comparison string for display."""
    change = calculate_change(current, previous)

    if change['status'] == 'no_change':
        return f"{prefix}{current:,.0f}{suffix} (no change)"

    arrow = '↑' if change['direction'] == 'up' else '↓' if change['direction'] == 'down' else '→'
    pct_str = f"{abs(change['percentage']):.1f}%"

    return f"{prefix}{current:,.0f}{suffix} ({arrow} {pct_str})"


def get_quick_date_ranges(max_date: date) -> dict:
    """
    Get quick date range options.

    Returns:
        Dictionary of {label: (start_date, end_date)}
    """
    today = max_date

    ranges = {
        'Today': (today, today),
        'Yesterday': (today - timedelta(days=1), today - timedelta(days=1)),
        'Last 7 Days': (today - timedelta(days=6), today),
        'Last 14 Days': (today - timedelta(days=13), today),
        'Last 30 Days': (today - timedelta(days=29), today),
        'Last 90 Days': (today - timedelta(days=89), today),
        'This Week': get_week_bounds(today),
        'Last Week': get_week_bounds(today - timedelta(weeks=1)),
        'This Month': (today.replace(day=1), today),
        'Last Month': get_last_month_bounds(today),
        'This Quarter': get_quarter_bounds(today),
        'Last Quarter': get_last_quarter_bounds(today),
        'This Year': (date(today.year, 1, 1), today),
        'Last Year': (date(today.year - 1, 1, 1), date(today.year - 1, 12, 31)),
        'All Time': None,  # Will be handled separately
    }

    return ranges


def get_week_bounds(d: date) -> Tuple[date, date]:
    """Get the start and end of the week containing date d."""
    start = d - timedelta(days=d.weekday())
    end = start + timedelta(days=6)
    return start, end


def get_last_month_bounds(d: date) -> Tuple[date, date]:
    """Get the bounds of the previous month."""
    first_of_this_month = d.replace(day=1)
    last_of_last_month = first_of_this_month - timedelta(days=1)
    first_of_last_month = last_of_last_month.replace(day=1)
    return first_of_last_month, last_of_last_month


def get_quarter_bounds(d: date) -> Tuple[date, date]:
    """Get the bounds of the current quarter."""
    quarter = (d.month - 1) // 3
    start_month = quarter * 3 + 1
    start = date(d.year, start_month, 1)

    if quarter == 3:
        end = date(d.year, 12, 31)
    else:
        end_month = start_month + 2
        end = date(d.year, end_month, 1) + timedelta(days=31)
        end = end.replace(day=1) - timedelta(days=1)

    return start, end


def get_last_quarter_bounds(d: date) -> Tuple[date, date]:
    """Get the bounds of the previous quarter."""
    quarter = (d.month - 1) // 3

    if quarter == 0:
        prev_quarter_year = d.year - 1
        prev_quarter = 3
    else:
        prev_quarter_year = d.year
        prev_quarter = quarter - 1

    start_month = prev_quarter * 3 + 1
    start = date(prev_quarter_year, start_month, 1)

    if prev_quarter == 3:
        end = date(prev_quarter_year, 12, 31)
    else:
        end_month = start_month + 2
        next_month = date(prev_quarter_year, end_month, 1) + timedelta(days=31)
        end = next_month.replace(day=1) - timedelta(days=1)

    return start, end


def format_period_label(start: date, end: date) -> str:
    """Format a date range as a readable label."""
    if start == end:
        return start.strftime('%b %d, %Y')

    if start.year == end.year:
        if start.month == end.month:
            return f"{start.strftime('%b')} {start.day}-{end.day}, {start.year}"
        else:
            return f"{start.strftime('%b %d')} - {end.strftime('%b %d, %Y')}"

    return f"{start.strftime('%b %d, %Y')} - {end.strftime('%b %d, %Y')}"
