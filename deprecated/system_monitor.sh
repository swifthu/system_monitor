#!/bin/bash
cd "$(dirname "$0")"

PID_FILE="/tmp/system_monitor.pid"

start() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat $PID_FILE)" 2>/dev/null; then
        echo "Already running (PID: $(cat $PID_FILE))"
        return 1
    fi
    ./server &
    echo $! > "$PID_FILE"
    echo "Started (PID: $(cat $PID_FILE))"
}

stop() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            rm -f "$PID_FILE"
            echo "Stopped (was: $PID)"
        else
            rm -f "$PID_FILE"
            echo "Stale PID file removed"
        fi
    else
        echo "Not running"
    fi
}

status() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat $PID_FILE)" 2>/dev/null; then
        echo "Running (PID: $(cat $PID_FILE))"
    else
        echo "Not running"
    fi
}

case "$1" in
    start) start ;;
    stop) stop ;;
    restart) stop; start ;;
    status) status ;;
    *) echo "Usage: $0 {start|stop|restart|status}" ;;
esac
