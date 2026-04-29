#!/bin/bash

# Rogius - Kokoro TTS Server Manager
# Usage: ./Rogius.sh [start|stop|restart|status]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KOKORO_SCRIPT="/home/roggoz/start-kokoro.sh"
PID_FILE="/tmp/kokoro.pid"
LOG_FILE="/tmp/kokoro.log"
PORT=8880

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if Kokoro is running
check_status() {
    if curl -s "http://localhost:${PORT}/" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to get PID from port
get_pid() {
    ss -tlnp 2>/dev/null | grep ":${PORT}" | grep -oP 'pid=\K[0-9]+' || echo ""
}

# Function to start Kokoro
start_kokoro() {
    if check_status; then
        echo -e "${GREEN}Kokoro is already running on port ${PORT}${NC}"
        echo -e "${YELLOW}Health check:${NC}"
        curl -s "http://localhost:${PORT}/" | python3 -m json.tool 2>/dev/null || curl -s "http://localhost:${PORT}/"
        return 0
    fi
    
    echo -e "${YELLOW}Starting Kokoro TTS Server...${NC}"
    
    # Kill any existing processes on the port
    local existing_pid=$(get_pid)
    if [ -n "$existing_pid" ]; then
        echo -e "${YELLOW}Killing existing process on port ${PORT} (PID: ${existing_pid})${NC}"
        kill -9 "$existing_pid" 2>/dev/null
        sleep 1
    fi
    
    # Start the server
    nohup bash "${KOKORO_SCRIPT}" > "${LOG_FILE}" 2>&1 &
    local new_pid=$!
    echo $new_pid > "${PID_FILE}"
    
    # Wait for it to be ready
    echo -e "${YELLOW}Waiting for server to start...${NC}"
    local attempts=0
    while [ $attempts -lt 30 ]; do
        if check_status; then
            echo -e "${GREEN}✓ Kokoro started successfully!${NC}"
            echo -e "${GREEN}  Endpoint: http://localhost:${PORT}/v1/audio/speech${NC}"
            echo -e "${GREEN}  Health:   http://localhost:${PORT}/${NC}"
            echo ""
            echo -e "${YELLOW}Health check:${NC}"
            curl -s "http://localhost:${PORT}/" | python3 -m json.tool 2>/dev/null || curl -s "http://localhost:${PORT}/"
            return 0
        fi
        sleep 1
        ((attempts++))
        echo -n "."
    done
    
    echo ""
    echo -e "${RED}✗ Failed to start Kokoro within 30 seconds${NC}"
    echo -e "${RED}Check logs: ${LOG_FILE}${NC}"
    tail -20 "${LOG_FILE}"
    return 1
}

# Function to stop Kokoro
stop_kokoro() {
    echo -e "${YELLOW}Stopping Kokoro TTS Server...${NC}"
    
    local pid=$(get_pid)
    if [ -n "$pid" ]; then
        kill -TERM "$pid" 2>/dev/null
        sleep 2
        
        # Force kill if still running
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null
        fi
        
        rm -f "${PID_FILE}"
        echo -e "${GREEN}✓ Kokoro stopped${NC}"
    else
        echo -e "${YELLOW}Kokoro was not running${NC}"
    fi
}

# Function to restart Kokoro
restart_kokoro() {
    echo -e "${YELLOW}Restarting Kokoro TTS Server...${NC}"
    stop_kokoro
    sleep 1
    start_kokoro
}

# Function to show status
show_status() {
    if check_status; then
        echo -e "${GREEN}Kokoro is RUNNING${NC}"
        echo -e "${YELLOW}Health check:${NC}"
        curl -s "http://localhost:${PORT}/" | python3 -m json.tool 2>/dev/null || curl -s "http://localhost:${PORT}/"
    else
        echo -e "${RED}Kokoro is NOT RUNNING${NC}"
    fi
}

# Function to show logs
show_logs() {
    if [ -f "${LOG_FILE}" ]; then
        echo -e "${YELLOW}Last 50 lines of Kokoro logs:${NC}"
        tail -50 "${LOG_FILE}"
    else
        echo -e "${RED}No log file found${NC}"
    fi
}

# Main command handler
case "${1:-start}" in
    start)
        start_kokoro
        ;;
    stop)
        stop_kokoro
        ;;
    restart)
        restart_kokoro
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    *)
        echo "Usage: $0 [start|stop|restart|status|logs]"
        echo ""
        echo "Commands:"
        echo "  start    - Start Kokoro if not running (default)"
        echo "  stop     - Stop Kokoro"
        echo "  restart  - Restart Kokoro"
        echo "  status   - Check if Kokoro is running"
        echo "  logs     - Show recent logs"
        exit 1
        ;;
esac
