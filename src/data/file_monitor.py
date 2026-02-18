"""
File monitor for auto-refreshing data when new files are added.
Watches BOTH 'Original files' and 'data' directories.
"""

import os
import time
import threading
import hashlib
from typing import Callable, List, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DATA_DIR

# Project root for resolving both data directories
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# All directories that contain data files
ALL_DATA_DIRS = [
    os.path.join(_PROJECT_ROOT, 'Original files'),
    os.path.join(_PROJECT_ROOT, 'data'),
]


class DataFileHandler(FileSystemEventHandler):
    """Handler for file system events in the data directory."""

    def __init__(self, callback: Callable, debounce_seconds: int = 5):
        super().__init__()
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self._last_trigger = 0
        self._pending_files = set()
        self._lock = threading.Lock()

    def _should_process(self, filepath: str) -> bool:
        """Check if file matches our data patterns."""
        filename = os.path.basename(filepath)

        # Check TikTok pattern (CSV files) - any CSV is a potential data file
        if filename.endswith('.csv') or filename.endswith('.csv.gz'):
            return True

        # Check Shopee pattern (Excel files)
        if filename.endswith('.xlsx'):
            return True

        # Ignore temp files
        if filename.endswith('.tmp') or filename.endswith('.crdownload'):
            return False

        return False

    def _debounced_callback(self):
        """Trigger callback with debouncing to avoid multiple rapid calls."""
        with self._lock:
            current_time = time.time()
            if current_time - self._last_trigger >= self.debounce_seconds:
                self._last_trigger = current_time
                # Run callback in background thread
                threading.Thread(target=self.callback, daemon=True).start()

    def on_created(self, event):
        """Handle file creation event."""
        if event.is_directory:
            return

        filepath = event.src_path
        if self._should_process(filepath):
            print(f"[Monitor] New file detected: {os.path.basename(filepath)}")
            with self._lock:
                self._pending_files.add(filepath)
            self._debounced_callback()

    def on_modified(self, event):
        """Handle file modification event."""
        if event.is_directory:
            return

        filepath = event.src_path
        if self._should_process(filepath):
            # Only trigger for significant modifications
            self._debounced_callback()

    def on_moved(self, event):
        """Handle file move/rename event (common when downloading)."""
        if event.is_directory:
            return

        filepath = event.dest_path
        if self._should_process(filepath):
            print(f"[Monitor] File moved/renamed: {os.path.basename(filepath)}")
            self._debounced_callback()


class DataMonitor:
    """Monitor for watching multiple data directories for changes."""

    def __init__(self, data_dirs: List[str] = None, refresh_callback: Callable = None):
        # Support multiple directories; fall back to both standard dirs
        if data_dirs is None:
            self.data_dirs = [d for d in ALL_DATA_DIRS]
        elif isinstance(data_dirs, str):
            self.data_dirs = [data_dirs]
        else:
            self.data_dirs = list(data_dirs)

        # Backward-compat single-dir attribute
        self.data_dir = self.data_dirs[0] if self.data_dirs else DATA_DIR

        self.refresh_callback = refresh_callback
        self.observer: Optional[Observer] = None
        self.handler: Optional[DataFileHandler] = None
        self._running = False
        self._file_hashes: dict = {}

    def _calculate_file_hash(self) -> dict:
        """Calculate hashes of all data files across ALL watched directories."""
        hashes = {}

        for data_dir in self.data_dirs:
            if not os.path.exists(data_dir):
                continue

            for filename in os.listdir(data_dir):
                filepath = os.path.join(data_dir, filename)

                if not os.path.isfile(filepath):
                    continue

                # Check if it's a data file
                if filename.endswith('.csv') or filename.endswith('.csv.gz') or filename.endswith('.xlsx'):
                    try:
                        with open(filepath, 'rb') as f:
                            # Read first and last 1MB for large files
                            f.seek(0, 2)
                            size = f.tell()

                            f.seek(0)
                            header = f.read(1024 * 1024)  # First 1MB

                            if size > 2 * 1024 * 1024:
                                f.seek(-1024 * 1024, 2)
                                footer = f.read(1024 * 1024)  # Last 1MB
                            else:
                                footer = b''

                            file_hash = hashlib.md5(header + footer).hexdigest()
                            # Use full path as key so same filename in different dirs are tracked separately
                            key = os.path.join(data_dir, filename)
                            hashes[key] = {'hash': file_hash, 'size': size}
                    except Exception as e:
                        print(f"[Monitor] Error hashing {filename}: {e}")

        return hashes

    def check_for_changes(self) -> bool:
        """Check if data files have changed since last check."""
        current_hashes = self._calculate_file_hash()

        if not self._file_hashes:
            self._file_hashes = current_hashes
            return False

        # Check for new files
        new_files = set(current_hashes.keys()) - set(self._file_hashes.keys())
        if new_files:
            new_names = [os.path.basename(f) for f in new_files]
            print(f"[Monitor] New files detected: {new_names}")
            self._file_hashes = current_hashes
            return True

        # Check for modified files (size or hash change)
        for filepath, info in current_hashes.items():
            old_info = self._file_hashes.get(filepath)
            if old_info:
                if old_info['size'] != info['size'] or old_info['hash'] != info['hash']:
                    print(f"[Monitor] Modified file detected: {os.path.basename(filepath)}")
                    self._file_hashes = current_hashes
                    return True

        return False

    def start_watching(self):
        """Start watching ALL data directories for changes."""
        if self._running:
            return

        self.handler = DataFileHandler(
            callback=self.refresh_callback,
            debounce_seconds=5
        )

        self.observer = Observer()
        watched_count = 0

        for data_dir in self.data_dirs:
            if os.path.exists(data_dir):
                self.observer.schedule(self.handler, data_dir, recursive=False)
                print(f"[Monitor] Watching directory: {data_dir}")
                watched_count += 1
            else:
                print(f"[Monitor] Directory not found (will not watch): {data_dir}")

        if watched_count == 0:
            print("[Monitor] No valid directories to watch")
            return

        self.observer.start()
        self._running = True

    def stop_watching(self):
        """Stop watching all directories."""
        if self.observer and self._running:
            self.observer.stop()
            self.observer.join()
            self._running = False
            print("[Monitor] Stopped watching")

    def is_running(self) -> bool:
        """Check if monitor is running."""
        return self._running


# Global monitor instance
_monitor: Optional[DataMonitor] = None


def get_monitor() -> DataMonitor:
    """Get or create the global monitor instance watching all data directories."""
    global _monitor
    if _monitor is None:
        _monitor = DataMonitor()
    return _monitor


def start_monitoring(refresh_callback: Callable):
    """Start monitoring all data directories with the given refresh callback."""
    global _monitor
    _monitor = DataMonitor(refresh_callback=refresh_callback)
    _monitor.start_watching()
    return _monitor


def stop_monitoring():
    """Stop monitoring."""
    global _monitor  # noqa: F824
    if _monitor:
        _monitor.stop_watching()


def check_for_new_data() -> bool:
    """Check if new data files have been added to any watched directory."""
    monitor = get_monitor()
    return monitor.check_for_changes()
