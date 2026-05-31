#!/bin/bash
set -e

# Wait for ollama to be ready
echo "Waiting for Ollama to be ready..."
for i in {1..30}; do
  if curl -s http://ollama:11434/api/tags > /dev/null 2>&1; then
    echo "Ollama is ready!"
    break
  fi
  echo "Attempt $i: Waiting for Ollama..."
  sleep 2
done

# Pull the model if it doesn't exist
MODEL_NAME=${MODEL_NAME:-llama3.2}
echo "Checking for model: $MODEL_NAME"

if ! curl -s http://ollama:11434/api/tags | grep -q "$MODEL_NAME"; then
  echo "Model $MODEL_NAME not found. Pulling..."
  curl -X POST http://ollama:11434/api/pull -d "{\"name\":\"$MODEL_NAME\"}" -H "Content-Type: application/json"
  echo "Model $MODEL_NAME pulled successfully"
else
  echo "Model $MODEL_NAME already exists"
fi

# Run the main application
echo "Starting Python application..."
if [ "${LOCAL_ONLY:-true}" = "true" ]; then
  exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
fi

exec python main.py
