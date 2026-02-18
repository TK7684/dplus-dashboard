#!/bin/bash
# Auto-monitor script for DPLUS Dashboard
# Watches 'Original files' AND 'data' directories and triggers DB refresh when new files are added

WATCH_DIR="/workspaces/DPLUS-Dashboard/Original files"
WATCH_DIR2="/workspaces/DPLUS-Dashboard/data"
LOG_FILE="/workspaces/DPLUS-Dashboard/monitor.log"

echo "$(date): File monitor started" >> "$LOG_FILE"
echo "$(date): Watching: $WATCH_DIR" >> "$LOG_FILE"
echo "$(date): Watching: $WATCH_DIR2" >> "$LOG_FILE"

# Check inotifywait is available
if ! command -v inotifywait &>/dev/null; then
    echo "$(date): ERROR - inotifywait not found. Install with: apt-get install inotify-tools" >> "$LOG_FILE"
    echo "inotifywait not found. Install with: apt-get install inotify-tools"
    exit 1
fi

# Ensure watch directories exist
mkdir -p "$WATCH_DIR" 2>/dev/null
mkdir -p "$WATCH_DIR2" 2>/dev/null

inotifywait -m -r -e create,moved_to,close_write \
    "$WATCH_DIR" "$WATCH_DIR2" 2>/dev/null | \
while read -r directory events filename; do
    # Only react to CSV and Excel files
    case "$filename" in
        *.csv|*.xlsx|*.csv.gz)
            echo "$(date): New/modified file detected: ${directory}${filename} ($events)" >> "$LOG_FILE"
            # Create a trigger file that the Streamlit app's file_monitor can detect
            touch /tmp/dplus_refresh_trigger
            echo "$(date): Refresh trigger created at /tmp/dplus_refresh_trigger" >> "$LOG_FILE"
            ;;
        *)
            # Ignore non-data files
            ;;
    esac
done
