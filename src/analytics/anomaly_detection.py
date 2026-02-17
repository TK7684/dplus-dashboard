"""
Anomaly detection for DPLUS Dashboard.
Identifies unusual patterns in revenue and performance metrics.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger import log_error


def detect_revenue_anomalies(
    data: pd.DataFrame,
    value_col: str = 'revenue',
    threshold: float = 2.0,
    method: str = 'zscore'
) -> pd.DataFrame:
    """
    Detect anomalous revenue days using statistical methods.

    Args:
        data: DataFrame with revenue data
        value_col: Column to analyze
        threshold: Number of standard deviations for anomaly threshold
        method: 'zscore' or 'iqr'

    Returns:
        DataFrame with anomaly flags and scores
    """
    if data.empty:
        return pd.DataFrame()

    try:
        df = data.copy()

        if value_col not in df.columns:
            return df

        values = df[value_col]

        if method == 'zscore':
            mean = values.mean()
            std = values.std()

            if std == 0:
                df['anomaly_score'] = 0
                df['is_anomaly'] = False
            else:
                df['anomaly_score'] = (values - mean) / std
                df['is_anomaly'] = abs(df['anomaly_score']) > threshold

        elif method == 'iqr':
            q1 = values.quantile(0.25)
            q3 = values.quantile(0.75)
            iqr = q3 - q1

            lower_bound = q1 - threshold * iqr
            upper_bound = q3 + threshold * iqr

            df['anomaly_score'] = values.apply(
                lambda x: (x - values.median()) / iqr if iqr > 0 else 0
            )
            df['is_anomaly'] = (values < lower_bound) | (values > upper_bound)

        # Classify anomaly type
        df['anomaly_type'] = df.apply(
            lambda row: 'spike' if row['anomaly_score'] > threshold else
            'drop' if row['anomaly_score'] < -threshold else 'normal',
            axis=1
        )

        return df

    except Exception as e:
        log_error(e, {'operation': 'detect_revenue_anomalies'})
        return data


def detect_performance_changes(
    current: Dict,
    previous: Dict,
    thresholds: Optional[Dict] = None
) -> List[Dict]:
    """
    Detect significant performance changes between periods.

    Args:
        current: Current period metrics
        previous: Previous period metrics
        thresholds: Custom thresholds for each metric

    Returns:
        List of alerts with severity levels
    """
    if thresholds is None:
        thresholds = {
            'revenue_drop': 0.20,
            'revenue_spike': 0.50,
            'aov_drop': 0.15,
            'aov_spike': 0.30,
            'orders_drop': 0.25,
            'orders_spike': 0.50
        }

    alerts = []

    try:
        metrics_to_check = [
            ('total_revenue', 'revenue', thresholds['revenue_drop'], thresholds['revenue_spike']),
            ('aov', 'AOV', thresholds['aov_drop'], thresholds['aov_spike']),
            ('total_orders', 'orders', thresholds['orders_drop'], thresholds['orders_spike'])
        ]

        for metric_key, metric_name, drop_thresh, spike_thresh in metrics_to_check:
            curr_val = current.get(metric_key, 0)
            prev_val = previous.get(metric_key, 0)

            if prev_val == 0:
                continue

            change_pct = (curr_val - prev_val) / prev_val

            if change_pct <= -drop_thresh:
                severity = 'critical' if change_pct <= -0.4 else 'warning'
                alerts.append({
                    'metric': metric_name,
                    'type': 'drop',
                    'severity': severity,
                    'change_pct': change_pct * 100,
                    'current': curr_val,
                    'previous': prev_val,
                    'message': f"{metric_name} dropped {abs(change_pct)*100:.1f}% ({prev_val:,.0f} to {curr_val:,.0f})"
                })
            elif change_pct >= spike_thresh:
                alerts.append({
                    'metric': metric_name,
                    'type': 'spike',
                    'severity': 'info',
                    'change_pct': change_pct * 100,
                    'current': curr_val,
                    'previous': prev_val,
                    'message': f"{metric_name} increased {change_pct*100:.1f}% ({prev_val:,.0f} to {curr_val:,.0f})"
                })

        # Sort by severity
        severity_order = {'critical': 0, 'warning': 1, 'info': 2}
        alerts.sort(key=lambda x: severity_order.get(x['severity'], 3))

        return alerts

    except Exception as e:
        log_error(e, {'operation': 'detect_performance_changes'})
        return []


def detect_consecutive_patterns(
    data: pd.DataFrame,
    value_col: str = 'revenue',
    min_consecutive: int = 3
) -> Dict:
    """
    Detect consecutive patterns (streaks) in data.

    Args:
        data: DataFrame with time series data
        value_col: Column to analyze
        min_consecutive: Minimum consecutive days to flag

    Returns:
        Dictionary with streak information
    """
    if data.empty or value_col not in data.columns:
        return {'declining_streak': 0, 'growing_streak': 0}

    try:
        df = data.copy().sort_values('date' if 'date' in data.columns else 'period')
        values = df[value_col].values

        # Calculate day-over-day changes
        changes = np.diff(values)

        # Find consecutive declining/growing streaks
        declining_streak = 0
        growing_streak = 0
        current_decline = 0
        current_growth = 0

        for change in changes:
            if change < 0:
                current_decline += 1
                current_growth = 0
                declining_streak = max(declining_streak, current_decline)
            elif change > 0:
                current_growth += 1
                current_decline = 0
                growing_streak = max(growing_streak, current_growth)
            else:
                current_decline = 0
                current_growth = 0

        return {
            'declining_streak': declining_streak,
            'growing_streak': growing_streak,
            'is_in_decline': declining_streak >= min_consecutive,
            'is_growing': growing_streak >= min_consecutive,
            'alert': declining_streak >= min_consecutive or growing_streak >= min_consecutive
        }

    except Exception as e:
        log_error(e, {'operation': 'detect_consecutive_patterns'})
        return {'declining_streak': 0, 'growing_streak': 0}


def calculate_volatility(
    data: pd.DataFrame,
    value_col: str = 'revenue',
    window: int = 7
) -> Dict:
    """
    Calculate revenue volatility metrics.

    Args:
        data: DataFrame with time series data
        value_col: Column to analyze
        window: Rolling window for calculations

    Returns:
        Dictionary with volatility metrics
    """
    if data.empty or value_col not in data.columns:
        return {'coefficient_of_variation': 0, 'volatility_level': 'unknown'}

    try:
        values = data[value_col]

        mean_val = values.mean()
        std_val = values.std()

        # Coefficient of variation
        cv = (std_val / mean_val * 100) if mean_val > 0 else 0

        # Rolling volatility
        rolling_std = values.rolling(window=window).std().iloc[-1] if len(values) >= window else std_val

        # Classify volatility
        if cv < 20:
            level = 'low'
        elif cv < 40:
            level = 'moderate'
        elif cv < 60:
            level = 'high'
        else:
            level = 'very_high'

        return {
            'coefficient_of_variation': cv,
            'standard_deviation': std_val,
            'mean': mean_val,
            'rolling_std': rolling_std,
            'volatility_level': level,
            'range': values.max() - values.min(),
            'range_pct': ((values.max() - values.min()) / mean_val * 100) if mean_val > 0 else 0
        }

    except Exception as e:
        log_error(e, {'operation': 'calculate_volatility'})
        return {'coefficient_of_variation': 0, 'volatility_level': 'error'}
