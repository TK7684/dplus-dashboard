"""
Alert management system for DPLUS Dashboard.
Monitors metrics and triggers alerts based on configurable thresholds.
"""

from typing import Dict, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger import log_error, log_info
from analytics.anomaly_detection import detect_performance_changes


class AlertSeverity(Enum):
    INFO = 'info'
    WARNING = 'warning'
    CRITICAL = 'critical'


@dataclass
class Alert:
    """Represents a single alert."""
    id: str
    metric: str
    severity: AlertSeverity
    message: str
    current_value: float
    threshold: float
    change_pct: float
    timestamp: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False
    details: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'metric': self.metric,
            'severity': self.severity.value,
            'message': self.message,
            'current_value': self.current_value,
            'threshold': self.threshold,
            'change_pct': self.change_pct,
            'timestamp': self.timestamp.isoformat(),
            'acknowledged': self.acknowledged,
            'details': self.details
        }


class AlertManager:
    """Manages alert configuration, detection, and notifications."""

    DEFAULT_THRESHOLDS = {
        'revenue_drop_critical': 0.30,    # 30% drop = critical
        'revenue_drop_warning': 0.20,     # 20% drop = warning
        'revenue_spike': 0.50,            # 50% spike = info
        'aov_drop_critical': 0.25,
        'aov_drop_warning': 0.15,
        'aov_spike': 0.30,
        'orders_drop_critical': 0.35,
        'orders_drop_warning': 0.25,
        'orders_spike': 0.50,
        'volatility_high': 0.40,          # CV > 40% = high volatility
    }

    def __init__(self, custom_thresholds: Optional[Dict] = None):
        self.thresholds = self.DEFAULT_THRESHOLDS.copy()
        if custom_thresholds:
            self.thresholds.update(custom_thresholds)

        self.active_alerts: List[Alert] = []
        self.alert_history: List[Alert] = []
        self.callbacks: List[Callable] = []
        self._alert_counter = 0

    def _generate_alert_id(self) -> str:
        self._alert_counter += 1
        return f"alert_{datetime.now().strftime('%Y%m%d')}_{self._alert_counter:04d}"

    def check_alerts(self, current: Dict, previous: Dict) -> List[Alert]:
        """
        Check all alert conditions and return new alerts.

        Args:
            current: Current period metrics
            previous: Previous period metrics for comparison

        Returns:
            List of new alerts triggered
        """
        new_alerts = []

        try:
            # Use anomaly detection for performance changes
            changes = detect_performance_changes(current, previous, {
                'revenue_drop': self.thresholds['revenue_drop_warning'],
                'revenue_spike': self.thresholds['revenue_spike'],
                'aov_drop': self.thresholds['aov_drop_warning'],
                'aov_spike': self.thresholds['aov_spike'],
                'orders_drop': self.thresholds['orders_drop_warning'],
                'orders_spike': self.thresholds['orders_spike']
            })

            for change in changes:
                metric_key = self._get_metric_key(change['metric'])
                severity = AlertSeverity(change['severity'])

                # Determine threshold based on severity
                if change['type'] == 'drop':
                    if severity == AlertSeverity.CRITICAL:
                        threshold = self.thresholds.get(f'{metric_key}_drop_critical', 0.3)
                    else:
                        threshold = self.thresholds.get(f'{metric_key}_drop_warning', 0.2)
                else:
                    threshold = self.thresholds.get(f'{metric_key}_spike', 0.5)

                alert = Alert(
                    id=self._generate_alert_id(),
                    metric=change['metric'],
                    severity=severity,
                    message=change['message'],
                    current_value=change['current'],
                    threshold=threshold,
                    change_pct=change['change_pct'],
                    details={
                        'type': change['type'],
                        'previous_value': change['previous']
                    }
                )

                new_alerts.append(alert)
                self.active_alerts.append(alert)
                self.alert_history.append(alert)

            # Trigger callbacks for new alerts
            for alert in new_alerts:
                for callback in self.callbacks:
                    try:
                        callback(alert)
                    except Exception as e:
                        log_error(e, {'operation': 'alert_callback', 'alert_id': alert.id})

            if new_alerts:
                log_info(f"Generated {len(new_alerts)} new alerts", {
                    'severities': [a.severity.value for a in new_alerts]
                })

            return new_alerts

        except Exception as e:
            log_error(e, {'operation': 'check_alerts'})
            return []

    def _get_metric_key(self, metric_name: str) -> str:
        """Convert metric name to config key."""
        mapping = {
            'revenue': 'revenue',
            'AOV': 'aov',
            'orders': 'orders'
        }
        return mapping.get(metric_name.lower(), metric_name.lower())

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Mark an alert as acknowledged."""
        for alert in self.active_alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                log_info(f"Alert acknowledged: {alert_id}")
                return True
        return False

    def clear_alert(self, alert_id: str) -> bool:
        """Remove an alert from active alerts."""
        for i, alert in enumerate(self.active_alerts):
            if alert.id == alert_id:
                self.active_alerts.pop(i)
                log_info(f"Alert cleared: {alert_id}")
                return True
        return False

    def clear_all_alerts(self):
        """Clear all active alerts."""
        count = len(self.active_alerts)
        self.active_alerts.clear()
        log_info(f"Cleared {count} active alerts")

    def get_active_alerts(self, severity: Optional[AlertSeverity] = None) -> List[Alert]:
        """Get active alerts, optionally filtered by severity."""
        if severity:
            return [a for a in self.active_alerts if a.severity == severity]
        return self.active_alerts.copy()

    def get_alert_summary(self) -> Dict:
        """Get summary of current alert state."""
        return {
            'total_active': len(self.active_alerts),
            'by_severity': {
                'critical': len([a for a in self.active_alerts if a.severity == AlertSeverity.CRITICAL]),
                'warning': len([a for a in self.active_alerts if a.severity == AlertSeverity.WARNING]),
                'info': len([a for a in self.active_alerts if a.severity == AlertSeverity.INFO])
            },
            'unacknowledged': len([a for a in self.active_alerts if not a.acknowledged]),
            'total_history': len(self.alert_history)
        }

    def register_callback(self, callback: Callable):
        """Register a callback to be called when alerts are triggered."""
        self.callbacks.append(callback)

    def update_thresholds(self, new_thresholds: Dict):
        """Update alert thresholds."""
        self.thresholds.update(new_thresholds)
        log_info("Alert thresholds updated", {'updates': list(new_thresholds.keys())})

    def format_alert_message(self, alert: Alert, format_type: str = 'text') -> str:
        """
        Format alert for display or notification.

        Args:
            alert: Alert to format
            format_type: 'text', 'html', or 'slack'

        Returns:
            Formatted message string
        """
        if format_type == 'html':
            return f"""
            <div style="padding: 10px; border-left: 4px solid {self._get_severity_color(alert.severity)};">
                <strong>[{alert.severity.value.upper()}]</strong> {alert.metric}<br>
                {alert.message}<br>
                <small>At {alert.timestamp.strftime('%Y-%m-%d %H:%M')}</small>
            </div>
            """
        elif format_type == 'slack':
            return f"*[{alert.severity.value.upper()}]* {alert.metric}\n{alert.message}"
        else:
            return f"[{alert.severity.value.upper()}] {alert.metric}: {alert.message}"

    def _get_severity_color(self, severity: AlertSeverity) -> str:
        """Get color for severity level."""
        colors = {
            AlertSeverity.CRITICAL: '#DC2626',
            AlertSeverity.WARNING: '#F59E0B',
            AlertSeverity.INFO: '#3B82F6'
        }
        return colors.get(severity, '#6B7280')


# Global alert manager instance
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Get or create the global alert manager instance."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager
