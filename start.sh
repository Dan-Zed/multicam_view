#!/bin/bash
# Start script for multicam view

# Check if already running
if pgrep -f "python run.py" > /dev/null; then
    echo "Multicam view is already running."
    exit 1
fi

# Create a log directory if it doesn't exist
mkdir -p logs

# Start the application with output logging
echo "Starting multicam view application..."
nohup poetry run python run.py > logs/multicam.log 2>&1 &

# Check if it started successfully
sleep 2
if pgrep -f "python run.py" > /dev/null; then
    echo "Multicam view started successfully! Access at http://$(hostname -I | awk '{print $1}'):8000"
    echo "To stop the application, run: ./stop.sh"
else
    echo "Failed to start multicam view. Check logs/multicam.log for details."
    exit 1
fi
