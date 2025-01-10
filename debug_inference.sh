#!/bin/bash

# debug_inference.sh
# Script to debug the Kokoro TTS system by running inference tests.

# Exit immediately if a command exits with a non-zero status
set -e

# Define project directory
PROJECT_DIR="$(pwd)"

# Load environment variables
if [[ -f "$PROJECT_DIR/.env" ]]; then
  # Automatically export all variables in .env
  set -a
  source "$PROJECT_DIR/.env"
  set +a
else
  echo "Error: .env file not found in $PROJECT_DIR"
  exit 1
fi

# Override DEBUG variable for debugging
export DEBUG=true

# Create OUTPUT_DIR if it doesn't exist
if [[ ! -d "$OUTPUT_DIR" ]]; then
  echo "Creating output directory at $OUTPUT_DIR..."
  mkdir -p "$OUTPUT_DIR"
fi

# Reset server.log
echo "Resetting server.log..."
> server.log

# Validate API key
if [[ -z "$API_KEY" || "$API_KEY" == "your_api_key_here" ]]; then
  echo "Error: API_KEY not set in .env file"
  exit 1
fi

# Launch Flask server with DEBUG=true
echo "Launching the Flask server with DEBUG=true..."
# Assuming server.py reads from environment variables
# Use nohup or a similar method to run the server in the background
python openai_kokoro_tts/server.py > server.log 2>&1 &
SERVER_PID=$!

# Function to clean up server process on exit
cleanup() {
  echo "Shutting down the Flask server..."
  kill $SERVER_PID
}
trap cleanup EXIT

# Wait for the server to start
sleep 5

# Test server connection
echo "Testing server connection..."
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:${PORT:-9090}/v1/models)

if [[ "$HTTP_STATUS" != "200" ]]; then
  echo "Error: Server not running properly. HTTP status: $HTTP_STATUS"
  echo "Displaying server.log:"
  cat server.log
  exit 1
fi

# Send inference request
TEXT="This is a test of the Kokoro TTS system."
VOICE="${DEFAULT_VOICE}"
RESPONSE_FORMAT="mp3"
echo "Sending inference request..."
HTTP_RESPONSE=$(curl -s -o "$OUTPUT_DIR/response.$RESPONSE_FORMAT" -w "%{http_code}" \
  -X POST http://localhost:${PORT:-9090}/v1/audio/speech \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
        \"input\": \"$TEXT\",
        \"voice\": \"$VOICE\",
        \"response_format\": \"$RESPONSE_FORMAT\"
      }")

if [[ "$HTTP_RESPONSE" == "200" ]]; then
  echo "Inference request successful. Response saved to $OUTPUT_DIR/response.$RESPONSE_FORMAT"
else
  echo "Inference request failed with HTTP status: $HTTP_RESPONSE"
  echo "Displaying server.log:"
  cat server.log
  exit 1
fi
