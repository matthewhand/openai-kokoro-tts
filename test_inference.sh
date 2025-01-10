#!/bin/bash

# Set the project directory (modify if needed)
PROJECT_DIR="$(pwd)"

# Load environment variables from .env
if [[ -f "$PROJECT_DIR/.env" ]]; then
  export $(grep -v '^#' "$PROJECT_DIR/.env" | xargs)
else
  echo "Error: .env file not found in $PROJECT_DIR"
  exit 1
fi

# Check if API_KEY is loaded
if [[ -z "$API_KEY" ]]; then
  echo "Error: API_KEY not set in .env file"
  exit 1
fi

# Launch the Flask server in the background
echo "Launching the Flask server..."
uv run openai_kokoro_tts/server.py > server.log 2>&1 &
SERVER_PID=$!

# Wait for the server to start
sleep 5

# Test the inference API
TEXT="This is a test of the Kokoro TTS system."
VOICE="af"
RESPONSE_FORMAT="mp3"

echo "Sending inference request..."
RESPONSE=$(curl -s -o response.mp3 -w "%{http_code}" \
  -X POST http://localhost:${PORT:-8000}/v1/audio/speech \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
        \"text\": \"$TEXT\",
        \"voice\": \"$VOICE\",
        \"response_format\": \"$RESPONSE_FORMAT\"
      }")

# Check the response status
if [[ "$RESPONSE" == "200" ]]; then
  echo "Inference request successful. Response saved to response.mp3"
else
  echo "Inference request failed with HTTP status: $RESPONSE"
  echo "Check server.log for more details."
fi

# Kill the Flask server
echo "Shutting down the Flask server..."
kill $SERVER_PID

