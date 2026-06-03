#!/bin/bash
set -e

echo "Waiting for Ollama to be ready..."
for i in {1..30}; do
  if curl -s http://ollama:11434/api/tags > /dev/null 2>&1; then
    echo "Ollama is ready!"
    break
  fi
  echo "Attempt $i: Waiting for Ollama..."
  sleep 2
done

CHAT_MODEL_NAME=${CHAT_MODEL_NAME:-${MODEL_NAME:-llama3.2:1b}}
SQL_MODEL_NAME=${SQL_MODEL_NAME:-qwen2.5-coder:7b-instruct-q4_K_M}
PULL_MODELS=${PULL_MODELS:-false}

pull_if_missing() {
  local model="$1"
  echo "Checking for model: $model"
  if curl -s http://ollama:11434/api/tags | grep -q "\"name\":\"$model\""; then
    echo "Model $model already present"
    return 0
  fi
  if [ "$PULL_MODELS" != "true" ]; then
    echo "Model $model NOT installed. Pull it manually with:"
    echo "  docker exec matrix-ollama ollama pull $model"
    return 0
  fi
  echo "Pulling $model (this may take a while)..."
  local resp
  resp=$(curl -s -X POST http://ollama:11434/api/pull \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"$model\",\"stream\":false}")
  if echo "$resp" | grep -q '"status":"success"'; then
    echo "Model $model pulled successfully"
  else
    echo "WARNING: failed to pull $model: $resp"
  fi
}

pull_if_missing "$CHAT_MODEL_NAME"
if [ "$SQL_MODEL_NAME" != "$CHAT_MODEL_NAME" ]; then
  pull_if_missing "$SQL_MODEL_NAME"
fi

echo "Installed models:"
curl -s http://ollama:11434/api/tags || true
echo

echo "Starting Python application..."
if [ "${LOCAL_ONLY:-true}" = "true" ]; then
  exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
fi

exec python main.py
