#!/bin/bash
# Watchdog script for multicam_view application
# This script monitors the application and restarts it if needed

LOG_FILE="watchdog.log"
MAX_RESTARTS=5
RESTART_TIMEOUT=300  # 5 minutes between restarts

# Function to log messages
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> $LOG_FILE
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Function to check if the application is responsive
check_app() {
    # Try to connect to the web interface
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000 | grep -q "200"; then
        return 0  # App is responsive
    else
        return 1  # App is not responsive
    fi
}

# Function to restart the application
restart_app() {
    log_message "Restarting multicam application..."
    
    # Stop the application
    ./stop.sh
    
    # Wait for app to fully stop
    sleep 5
    
    # Kill any remaining processes
    pkill -f "python.*run.py" || true
    
    # Wait for processes to die
    sleep 2
    
    # Start the application
    ./start.sh
    
    # Wait for app to start
    sleep 10
    
    log_message "Restart complete."
}

# Main loop
log_message "Starting watchdog for multicam application"
restart_count=0
last_restart_time=0

while true; do
    # Check if we can restart
    current_time=$(date +%s)
    time_since_last_restart=$((current_time - last_restart_time))
    
    # Check if the app is responsive
    if ! check_app; then
        log_message "Application appears to be unresponsive"
        
        # Check if we've reached the maximum restarts
        if [ $restart_count -ge $MAX_RESTARTS ]; then
            log_message "Maximum restarts ($MAX_RESTARTS) reached. Will not restart automatically."
            log_message "Please check the system and restart manually."
            exit 1
        fi
        
        # Check if we need to wait before restarting
        if [ $time_since_last_restart -lt $RESTART_TIMEOUT ] && [ $restart_count -gt 0 ]; then
            wait_time=$((RESTART_TIMEOUT - time_since_last_restart))
            log_message "Waiting $wait_time seconds before restarting..."
            sleep $wait_time
        fi
        
        # Restart the app
        restart_app
        restart_count=$((restart_count + 1))
        last_restart_time=$(date +%s)
        log_message "Restart count: $restart_count/$MAX_RESTARTS"
    else
        # App is responsive, reset restart count if it's been a while
        if [ $time_since_last_restart -gt $RESTART_TIMEOUT ] && [ $restart_count -gt 0 ]; then
            log_message "Application has been stable for over $RESTART_TIMEOUT seconds, resetting restart count."
            restart_count=0
        fi
    fi
    
    # Wait before next check
    sleep 30
done
