"""
Data Validation Module for DPLUS Dashboard.
Provides validation checks before and after database operations to ensure data integrity.
"""

import pandas as pd
import duckdb
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ValidationResult:
    """Result of a validation check."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    stats: Dict


class DataValidator:
    """Validates data integrity before and after operations."""

    def __init__(self):
        self.errors = []
        self.warnings = []

    def reset(self):
        """Reset validation state."""
        self.errors = []
        self.warnings = []

    def validate_source_files(self, files: Dict[str, List[str]]) -> ValidationResult:
        """
        Validate source files are readable and properly formatted.

        Args:
            files: Dict with 'tiktok' and 'shopee' keys containing file paths

        Returns:
            ValidationResult with file validation status
        """
        errors = []
        warnings = []
        stats = {
            'tiktok_files': 0,
            'shopee_files': 0,
            'total_files': 0
        }

        # Check TikTok files
        tiktok_files = files.get('tiktok', [])
        for filepath in tiktok_files:
            try:
                # Check file is readable
                with open(filepath, 'rb') as f:
                    header = f.read(1024)
                    if not header:
                        errors.append(f"TikTok file is empty: {filepath}")
            except Exception as e:
                errors.append(f"Cannot read TikTok file {filepath}: {str(e)}")

        stats['tiktok_files'] = len(tiktok_files)

        # Check Shopee files
        shopee_files = files.get('shopee', [])
        for filepath in shopee_files:
            try:
                with open(filepath, 'rb') as f:
                    header = f.read(1024)
                    if not header:
                        errors.append(f"Shopee file is empty: {filepath}")
            except Exception as e:
                errors.append(f"Cannot read Shopee file {filepath}: {str(e)}")

        stats['shopee_files'] = len(shopee_files)
        stats['total_files'] = len(tiktok_files) + len(shopee_files)

        if stats['total_files'] == 0:
            warnings.append("No data files found")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            stats=stats
        )

    def validate_order_uniqueness(self, df: pd.DataFrame, platform: str) -> ValidationResult:
        """
        Check for duplicate order_ids within platform.

        Args:
            df: DataFrame with order data
            platform: Platform name ('TikTok' or 'Shopee')

        Returns:
            ValidationResult with uniqueness validation status
        """
        errors = []
        warnings = []
        stats = {
            'total_records': len(df),
            'unique_orders': 0,
            'duplicate_count': 0,
            'duplicate_order_ids': []
        }

        if df.empty:
            return ValidationResult(
                is_valid=True,
                errors=[],
                warnings=['Empty DataFrame provided'],
                stats=stats
            )

        if 'order_id' not in df.columns:
            errors.append("Missing 'order_id' column")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                stats=stats
            )

        # Count unique order IDs
        stats['unique_orders'] = df['order_id'].nunique()
        stats['duplicate_count'] = len(df) - stats['unique_orders']

        # Find duplicate order IDs
        duplicates = df[df.duplicated(subset=['order_id'], keep=False)]
        if not duplicates.empty:
            duplicate_ids = duplicates['order_id'].unique().tolist()[:10]
            stats['duplicate_order_ids'] = duplicate_ids
            warnings.append(f"Found {stats['duplicate_count']} duplicate records in {platform} data")
            warnings.append(f"Sample duplicate order_ids: {duplicate_ids[:5]}")

        return ValidationResult(
            is_valid=True,  # Duplicates are warnings, not errors
            errors=errors,
            warnings=warnings,
            stats=stats
        )

    def validate_required_fields(self, df: pd.DataFrame) -> ValidationResult:
        """
        Ensure required fields are present and non-empty.

        Args:
            df: DataFrame with order data

        Returns:
            ValidationResult with required fields validation status
        """
        errors = []
        warnings = []
        stats = {}

        required_fields = ['order_id', 'product_name', 'subtotal_net', 'created_at']

        for field in required_fields:
            if field not in df.columns:
                errors.append(f"Missing required field: {field}")
            else:
                null_count = df[field].isna().sum()
                empty_count = (df[field].astype(str).str.strip() == '').sum()
                stats[field] = {
                    'null_count': null_count,
                    'empty_count': empty_count,
                    'valid_count': len(df) - null_count - empty_count
                }
                if null_count > 0:
                    warnings.append(f"Field '{field}' has {null_count} null values")
                if empty_count > 0:
                    warnings.append(f"Field '{field}' has {empty_count} empty values")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            stats=stats
        )

    def validate_date_ranges(self, df: pd.DataFrame) -> ValidationResult:
        """
        Check dates are within reasonable bounds.

        Args:
            df: DataFrame with date data

        Returns:
            ValidationResult with date range validation status
        """
        errors = []
        warnings = []
        stats = {}

        if 'date' not in df.columns or df.empty:
            return ValidationResult(
                is_valid=True,
                errors=[],
                warnings=['No date column or empty DataFrame'],
                stats=stats
            )

        min_date = df['date'].min()
        max_date = df['date'].max()
        stats['min_date'] = str(min_date)
        stats['max_date'] = str(max_date)

        from datetime import date
        today = date.today()

        # Check for dates too far in the past
        if hasattr(min_date, 'year') and min_date.year < 2020:
            warnings.append(f"Data contains records from before 2020: {min_date}")

        # Check for dates in the future
        if hasattr(max_date, 'year') and max_date > today:
            warnings.append(f"Data contains future dates: {max_date}")

        # Count records with invalid dates
        if 'created_at' in df.columns:
            invalid_dates = df[df['created_at'].isna()]
            if not invalid_dates.empty:
                stats['invalid_date_count'] = len(invalid_dates)
                warnings.append(f"Found {len(invalid_dates)} records with invalid dates")

        return ValidationResult(
            is_valid=True,
            errors=errors,
            warnings=warnings,
            stats=stats
        )

    def validate_before_update(
        self,
        current_stats: Dict,
        new_stats: Dict,
        threshold: float = 0.1
    ) -> ValidationResult:
        """
        Final validation before database update.

        Args:
            current_stats: Current database statistics
            new_stats: New data statistics
            threshold: Acceptable change threshold (default 10%)

        Returns:
            ValidationResult with pre-update validation status
        """
        errors = []
        warnings = []
        stats = {
            'current_rows': current_stats.get('total_rows', 0),
            'new_rows': new_stats.get('total_rows', 0),
            'row_change': 0,
            'row_change_pct': 0
        }

        current_rows = current_stats.get('total_rows', 0)
        new_rows = new_stats.get('total_rows', 0)

        stats['row_change'] = new_rows - current_rows

        if current_rows > 0:
            stats['row_change_pct'] = ((new_rows - current_rows) / current_rows) * 100
        else:
            stats['row_change_pct'] = 100 if new_rows > 0 else 0

        # Check for significant data loss
        if new_rows < current_rows * (1 - threshold):
            data_loss_pct = ((current_rows - new_rows) / current_rows) * 100
            errors.append(
                f"Potential data loss: {current_rows:,} -> {new_rows:,} "
                f"({data_loss_pct:.1f}% decrease)"
            )

        # Check for unexpected large increase
        if new_rows > current_rows * (1 + 5 * threshold) and current_rows > 0:
            data_gain_pct = ((new_rows - current_rows) / current_rows) * 100
            warnings.append(
                f"Large data increase: {current_rows:,} -> {new_rows:,} "
                f"({data_gain_pct:.1f}% increase)"
            )

        # Check for duplicate increase
        new_duplicates = new_stats.get('duplicate_count', 0)
        if new_duplicates > 0:
            warnings.append(f"Found {new_duplicates} duplicate records in new data")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            stats=stats
        )

    def check_database_integrity(self, conn) -> ValidationResult:
        """
        Run integrity checks on database.

        Args:
            conn: DuckDB connection

        Returns:
            ValidationResult with database integrity status
        """
        errors = []
        warnings = []
        stats = {}

        try:
            # Check 1: Duplicate order_id + platform
            dup_check = conn.execute('''
                SELECT COUNT(*) FROM (
                    SELECT order_id, platform FROM orders
                    GROUP BY order_id, platform HAVING COUNT(*) > 1
                )
            ''').fetchone()[0]

            stats['duplicate_order_platform'] = dup_check
            if dup_check > 0:
                errors.append(f"Found {dup_check} duplicate order_id+platform combinations")

            # Check 2: Empty order_ids
            empty_check = conn.execute(
                "SELECT COUNT(*) FROM orders WHERE order_id IS NULL OR order_id = ''"
            ).fetchone()[0]

            stats['empty_order_ids'] = empty_check
            if empty_check > 0:
                warnings.append(f"Found {empty_check} records with empty order_id")

            # Check 3: Invalid dates
            invalid_dates = conn.execute('''
                SELECT COUNT(*) FROM orders
                WHERE date IS NULL
            ''').fetchone()[0]

            stats['invalid_dates'] = invalid_dates
            if invalid_dates > 0:
                warnings.append(f"Found {invalid_dates} records with NULL date")

            # Check 4: Missing product names
            missing_products = conn.execute('''
                SELECT COUNT(*) FROM orders
                WHERE product_name IS NULL OR product_name = ''
            ''').fetchone()[0]

            stats['missing_product_names'] = missing_products
            if missing_products > 0:
                warnings.append(f"Found {missing_products} records with missing product_name")

            # Check 5: Negative values
            negative_revenue = conn.execute('''
                SELECT COUNT(*) FROM orders WHERE subtotal_net < 0
            ''').fetchone()[0]

            stats['negative_revenue_records'] = negative_revenue
            if negative_revenue > 0:
                warnings.append(f"Found {negative_revenue} records with negative revenue")

            # Get total count
            stats['total_records'] = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            stats['unique_orders'] = conn.execute("SELECT COUNT(DISTINCT order_id) FROM orders").fetchone()[0]

        except Exception as e:
            errors.append(f"Database integrity check failed: {str(e)}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            stats=stats
        )


class DataOperationsLogger:
    """Logger for data operations."""

    def __init__(self, conn):
        self.conn = conn
        self._ensure_table_exists()

    def _ensure_table_exists(self):
        """Create operations log table if it doesn't exist."""
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS data_operations_log (
                id INTEGER PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                operation VARCHAR,
                platform VARCHAR,
                files_processed INTEGER,
                records_added INTEGER,
                duplicates_removed INTEGER,
                status VARCHAR,
                error_message VARCHAR,
                validation_warnings VARCHAR
            )
        ''')

    def log_operation(
        self,
        operation: str,
        platform: str,
        stats: Dict,
        status: str,
        error: str = None
    ):
        """
        Log a data operation.

        Args:
            operation: Operation type ('load', 'refresh', 'validate', 'build')
            platform: Platform name ('TikTok', 'Shopee', 'All')
            stats: Dictionary with operation statistics
            status: Operation status ('success', 'warning', 'error')
            error: Error message if any
        """
        warnings_str = '; '.join(stats.get('warnings', [])) if stats.get('warnings') else None

        self.conn.execute('''
            INSERT INTO data_operations_log (
                timestamp, operation, platform, files_processed,
                records_added, duplicates_removed, status,
                error_message, validation_warnings
            ) VALUES (
                CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?
            )
        ''', [
            operation,
            platform,
            stats.get('files_processed', 0),
            stats.get('records_added', 0),
            stats.get('duplicates_removed', 0),
            status,
            error,
            warnings_str
        ])

    def get_recent_operations(self, limit: int = 100) -> List[Dict]:
        """
        Get recent operations from log.

        Args:
            limit: Maximum number of operations to return

        Returns:
            List of operation records
        """
        result = self.conn.execute('''
            SELECT * FROM data_operations_log
            ORDER BY timestamp DESC
            LIMIT ?
        ''', [limit]).fetchdf()

        return result.to_dict('records')

    def get_failed_operations(self) -> List[Dict]:
        """Get failed operations from log."""
        result = self.conn.execute('''
            SELECT * FROM data_operations_log
            WHERE status = 'error'
            ORDER BY timestamp DESC
        ''').fetchdf()

        return result.to_dict('records')
