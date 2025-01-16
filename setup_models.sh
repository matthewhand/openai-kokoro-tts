#!/bin/bash

# Variables for model and voice directories
MODEL_REPO="https://huggingface.co/hexgrad/Kokoro-82M"
MODEL_DIR="models/kokoro"
VOICE_DIR="voices"
VOICES_JSON_URL="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.json"

# Function to print status messages in bold blue text
print_status() {
  echo -e "\\033[1;34m$1\\033[0m"
}

# Step 1: Ensure Git LFS is installed
print_status "Checking Git LFS installation..."
if ! command -v git-lfs &> /dev/null; then
  echo "Git LFS is not installed. Installing now..."
  sudo apt-get update && sudo apt-get install -y git-lfs
  if [[ $? -ne 0 ]]; then
    echo "Error: Failed to install Git LFS. Please install it manually and re-run the script."
    exit 1
  fi
fi
git lfs install

# Step 2: Clone the Kokoro-82M model repository
print_status "Cloning the Kokoro-82M repository..."
if [[ -d "$MODEL_DIR" ]]; then
  echo "Model directory '$MODEL_DIR' already exists. Skipping clone."
else
  git clone "$MODEL_REPO" "$MODEL_DIR"
  if [[ $? -ne 0 ]]; then
    echo "Error: Failed to clone the Kokoro model repository. Check your internet connection and try again."
    exit 1
  fi
fi

# Step 3: Install required system dependencies (espeak-ng)
print_status "Installing system dependencies..."
sudo apt-get update && sudo apt-get -qq -y install espeak-ng > /dev/null 2>&1
if [[ $? -ne 0 ]]; then
  echo "Error: Failed to install espeak-ng. Check your permissions or package manager configuration."
  exit 1
fi

# Step 4: Verify the model file exists
print_status "Verifying model file availability..."
if [[ ! -f "$MODEL_DIR/kokoro-v0_19.pth" ]]; then
  echo "Error: Model file 'kokoro-v0_19.pth' is missing in $MODEL_DIR."
  exit 1
fi

# Step 5: Download voices.json
print_status "Downloading voices.json configuration..."
curl -L "$VOICES_JSON_URL" -o "$MODEL_DIR/voices.json"
if [[ $? -ne 0 ]]; then
  echo "Error: Failed to download voices.json. Check your internet connection and try again."
  exit 1
fi

# Step 6: Display setup success
print_status "Model and dependencies have been successfully set up!"
echo "Model directory: $MODEL_DIR"
echo "Voice directory: $VOICE_DIR"
