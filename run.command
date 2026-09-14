#!/bin/bash
# run.command — double-click in Finder to start pdf-perfcut

# Change to the directory containing this script
cd "$(dirname "$0")"

PORT=8765
URL="http://localhost:$PORT"

echo "=== pdf-perfcut ==="
echo "Starting server on $URL"

# Free the port if something is already listening on it
lsof -ti tcp:$PORT | xargs kill -9 2>/dev/null || true

# Open browser after a short delay so the server has time to start
(sleep 1.5 && open "$URL") &

# Start uvicorn using the Python that has the packages installed
/Library/Developer/CommandLineTools/usr/bin/python3 -m uvicorn app.main:app \
    --host 127.0.0.1 \
    --port $PORT \
    --log-level warning
