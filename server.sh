#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

case "$1" in
  start)
    if pgrep -f "uvicorn main:app" > /dev/null; then
      echo "Server already running"
    else
      nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/server.log 2>&1 &
      sleep 2
      echo "Server started on http://$(hostname -I | awk '{print $1}'):8000"
    fi
    ;;
  stop)
    pkill -f "uvicorn main:app" && echo "Server stopped" || echo "No server running"
    ;;
  restart)
    pkill -f "uvicorn main:app" 2>/dev/null
    sleep 1
    nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/server.log 2>&1 &
    sleep 2
    echo "Server restarted on http://$(hostname -I | awk '{print $1}'):8000"
    ;;
  status)
    if pgrep -f "uvicorn main:app" > /dev/null; then
      echo "Server running on port 8000"
    else
      echo "Server not running"
    fi
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status}"
    ;;
esac
