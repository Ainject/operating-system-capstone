#!/bin/sh
# Run the simulator on localhost: http://127.0.0.1:8000
cd "$(dirname "$0")"
exec python3 app.py --host 127.0.0.1 --port 8000
