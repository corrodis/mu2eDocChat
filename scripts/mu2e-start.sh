#!/bin/bash

# mu2e-start.sh - manage all the mu2e services in a screen session
# Usage: ./mu2e-start.sh [--force-restart]

FORCE_RESTART=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --force-restart|-f)
            FORCE_RESTART=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--force-restart]"
            echo "  --force-restart, -f    Kill existing sessions and restart"
            echo "  --help, -h            Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Define services
declare -A SERVICES=(
    ["mu2e-slack"]="mu2e-slack"
    ["mu2e-web"]="mu2e-web"
    ["mu2e-mcp-http"]="mu2e-mcp-server --collection argo --port 1223"
)

# Function to check if screen session exists
session_exists() {
    screen -list | grep -q "\.${1}[[:space:]]"
}

# Function to start a service in screen
start_service() {
    local session_name="$1"
    local command="$2"
    
    echo "Starting $session_name..."
    screen -dmS "$session_name" bash -c "$command"
    
    # Give it a moment to start
    sleep 1
    
    # Check if session was created successfully
    if session_exists "$session_name"; then
        echo "✓ $session_name started successfully"
    else
        echo "✗ Failed to start $session_name"
    fi
}

# Function to kill a screen session
kill_session() {
    local session_name="$1"
    echo "Killing existing session: $session_name"
    screen -S "$session_name" -X quit
    sleep 1
}

# Main logic
echo "Managing mu2e services..."
echo "Force restart mode: $FORCE_RESTART"
echo

for session_name in "${!SERVICES[@]}"; do
    command="${SERVICES[$session_name]}"
    
    if session_exists "$session_name"; then
        if $FORCE_RESTART; then
            kill_session "$session_name"
            start_service "$session_name" "$command"
        else
            echo "✓ $session_name is already running (keeping alive)"
        fi
    else
        start_service "$session_name" "$command"
    fi
done

echo
echo "Current screen sessions:"
screen -list | grep -E "(mu2e-slack|mu2e-web|mu2e-mcp)" || echo "No mu2e sessions found"

echo
echo "To attach to a session, use: screen -r <session_name>"
echo "To list all sessions, use: screen -list"
echo "To detach from a session, use: Ctrl+A then D"
