#!/bin/bash
set -e

echo "Starting Python application..."
if [ "${LOCAL_ONLY:-true}" = "true" ]; then
  exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
fi

exec python main.py
