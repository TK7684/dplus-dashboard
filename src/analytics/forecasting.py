"""
Trend forecasting and statistical analysis for DPLUS Dashboard.
"""

import pandas as pd
import numpy as np
from typing import Dict
from datetime import timedelta
from scipy import stats
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger import log_error


def forecast_revenue(
    historical_data: pd.DataFrame,
    periods: int = 30,
    confidence_level: float = 0.95
) -> Dict:
    """
    Forecast future revenue using linear regression.

    Args:
        historical_data: DataFrame with 'date' and 'revenue' columns
        periods: Number of periods to forecast
        confidence_level: Confidence level for intervals (0-1)

    Returns:
        Dictionary with forecast data, trend info, and confidence intervals
    """
    if historical_data.empty or len(historical_data) < 5:
        return {
            'forecast': None,
            'trend': 'insufficient_data',
            'slope': 0,
            'r_squared': 0,
            'message': 'Need at least 5 data points for forecasting'
        }

    try:
        df = historical_data.copy()
        df = df.sort_values('date')

        # Convert dates to numeric (days since first date)
        if 'period' in df.columns:
            df['date'] = pd.to_datetime(df['period'])
        else:
            df['date'] = pd.to_datetime(df['date'])

        first_date = df['date'].min()
        df['days'] = (df['date'] - first_date).dt.days

        # Aggregate by date if needed
        if 'revenue' not in df.columns:
            return {'forecast': None, 'trend': 'error', 'message': 'No revenue column'}

        daily_revenue = df.groupby('days')['revenue'].sum().reset_index()
        x = daily_revenue['days'].values
        y = daily_revenue['revenue'].values

        # Linear regression
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

        # Calculate forecast
        last_day = x.max()
        forecast_days = np.arange(last_day + 1, last_day + periods + 1)
        forecast_values = intercept + slope * forecast_days

        # Confidence intervals
        n = len(x)
        mean_x = np.mean(x)
        ss_x = np.sum((x - mean_x) ** 2)
        se_y = np.sqrt(np.sum((y - (intercept + slope * x)) ** 2) / (n - 2))

        # t-value for confidence level
        t_val = stats.t.ppf((1 + confidence_level) / 2, n - 2)

        # Confidence interval for each forecast point
        se_pred = se_y * np.sqrt(1 + 1/n + (forecast_days - mean_x)**2 / ss_x)
        ci_lower = forecast_values - t_val * se_pred
        ci_upper = forecast_values + t_val * se_pred

        # Ensure non-negative forecasts
        forecast_values = np.maximum(forecast_values, 0)
        ci_lower = np.maximum(ci_lower, 0)

        # Generate forecast dates
        forecast_dates = [first_date + timedelta(days=int(d)) for d in forecast_days]

        # Determine trend direction
        if slope > 0 and p_value < 0.05:
            trend = 'increasing'
        elif slope < 0 and p_value < 0.05:
            trend = 'decreasing'
        else:
            trend = 'stable'

        return {
            'forecast': pd.DataFrame({
                'date': forecast_dates,
                'predicted_revenue': forecast_values,
                'ci_lower': ci_lower,
                'ci_upper': ci_upper
            }),
            'trend': trend,
            'slope': slope,
            'intercept': intercept,
            'r_squared': r_value ** 2,
            'p_value': p_value,
            'confidence_level': confidence_level,
            'daily_change': slope,
            'projected_total': forecast_values.sum(),
            'message': None
        }

    except Exception as e:
        log_error(e, {'operation': 'forecast_revenue'})
        return {'forecast': None, 'trend': 'error', 'message': str(e)}


def calculate_trend_significance(data: pd.Series) -> Dict:
    """
    Calculate statistical significance of trends.

    Args:
        data: Time series data

    Returns:
        Dictionary with trend statistics
    """
    if len(data) < 3:
        return {
            'slope': 0,
            'p_value': 1.0,
            'r_squared': 0,
            'direction': 'insufficient_data',
            'significant': False
        }

    try:
        x = np.arange(len(data))
        y = data.values

        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

        if slope > 0:
            direction = 'upward'
        elif slope < 0:
            direction = 'downward'
        else:
            direction = 'flat'

        return {
            'slope': slope,
            'intercept': intercept,
            'p_value': p_value,
            'r_squared': r_value ** 2,
            'direction': direction,
            'significant': p_value < 0.05,
            'change_per_period': slope,
            'percent_change': (slope / data.mean() * 100) if data.mean() != 0 else 0
        }

    except Exception as e:
        log_error(e, {'operation': 'calculate_trend_significance'})
        return {
            'slope': 0,
            'p_value': 1.0,
            'r_squared': 0,
            'direction': 'error',
            'significant': False
        }


def calculate_moving_average(
    data: pd.DataFrame,
    value_col: str = 'revenue',
    window: int = 7
) -> pd.DataFrame:
    """
    Calculate moving average for smoothing.

    Args:
        data: DataFrame with time series data
        value_col: Column to average
        window: Window size in days

    Returns:
        DataFrame with added moving average column
    """
    df = data.copy()

    if value_col not in df.columns:
        return df

    df[f'{value_col}_ma_{window}'] = df[value_col].rolling(window=window, min_periods=1).mean()

    return df


def calculate_seasonality(
    data: pd.DataFrame,
    value_col: str = 'revenue',
    period: str = 'weekly'
) -> Dict:
    """
    Calculate seasonality patterns.

    Args:
        data: DataFrame with date and value columns
        value_col: Column to analyze
        period: 'weekly' or 'monthly'

    Returns:
        Dictionary with seasonality indices
    """
    try:
        df = data.copy()

        if 'date' not in df.columns and 'period' in df.columns:
            df['date'] = pd.to_datetime(df['period'])
        elif 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        else:
            return {'pattern': None, 'message': 'No date column'}

        if period == 'weekly':
            df['period_idx'] = df['date'].dt.dayofweek
            period_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        else:  # monthly
            df['period_idx'] = df['date'].dt.month
            period_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                            'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

        # Calculate average for each period
        overall_avg = df[value_col].mean()
        period_avgs = df.groupby('period_idx')[value_col].mean()

        # Seasonality index (1.0 = average, >1 = above average)
        indices = (period_avgs / overall_avg).to_dict()

        return {
            'pattern': period,
            'indices': {period_names.get(k, str(k)): v for k, v in indices.items()},
            'best_period': period_names[period_avgs.idxmax()],
            'worst_period': period_names[period_avgs.idxmin()],
            'overall_average': overall_avg
        }

    except Exception as e:
        log_error(e, {'operation': 'calculate_seasonality'})
        return {'pattern': None, 'message': str(e)}
