#!/bin/bash
# Stop script for multicam view

# Find and kill the process
PID=$(pgrep -f "python run.py")
if [ -z "$PID" ]; then
    echo "Multicam view is not running."
    exit 0
fi

echo "Stopping multicam view (PID: $PID)..."
kill $PID

# Check if it was killed
sleep 2
if pgrep -f "python run.py" > /dev/null; then
    echo "Failed to stop multicam view gracefully. Forcing termination..."
    kill -9 $PID
    sleep 1
fi

if pgrep -f "python3 run.py" > /dev/null; then
    echo "Failed to stop multicam view. Please check manually."
    exit 1
else
    echo "Multicam view stopped successfully."
fi
