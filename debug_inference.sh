#!/bin/bash

# Define project directory
PROJECT_DIR="$(pwd)"

# Load environment variables
if [[ -f "$PROJECT_DIR/.env" ]]; then
  export $(grep -v '^#' "$PROJECT_DIR/.env" | xargs)
else
  echo "Error: .env file not found in $PROJECT_DIR"
  exit 1
fi

# Override DEBUG variable for debugging
export DEBUG=true

# Reset server.log
echo "Resetting server.log..."
> server.log

# Validate API key
if [[ -z "$API_KEY" ]]; then
  echo "Error: API_KEY not set in .env file"
  exit 1
fi

# Launch Flask server with DEBUG=true
echo "Launching the Flask server with DEBUG=true..."
uv run openai_kokoro_tts/server.py > server.log 2>&1 &
SERVER_PID=$!

# Wait for the server to start
sleep 5

# Test server connection
echo "Testing server connection..."
curl -s http://localhost:${PORT:-9090}/v1/models > /dev/null
if [[ $? -ne 0 ]]; then
  echo "Error: Server not running. Displaying server.log:"
  cat server.log
  kill $SERVER_PID
  exit 1
fi

# Send inference request
TEXT="This is a test of the Kokoro TTS system."
VOICE="af"
RESPONSE_FORMAT="mp3"
echo "Sending inference request..."
RESPONSE=$(curl -s -o response.mp3 -w "%{http_code}" \
  -X POST http://localhost:${PORT:-9090}/v1/audio/speech \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
        \"text\": \"$TEXT\",
        \"voice\": \"$VOICE\",
        \"response_format\": \"$RESPONSE_FORMAT\"
      }")

if [[ "$RESPONSE" == "200" ]]; then
  echo "Inference request successful. Response saved to response.mp3"
else
  echo "Inference request failed with HTTP status: $RESPONSE"
  echo "Displaying server.log:"
  cat server.log
fi

# Shut down Flask server
echo "Shutting down the Flask server..."
kill $SERVER_PID
