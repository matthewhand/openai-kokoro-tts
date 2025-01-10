#!/bin/bash

# Define variables
MODEL_REPO="https://huggingface.co/hexgrad/Kokoro-82M"
MODEL_DIR="models/kokoro"
VOICE_DIR="voices"

# Function to print status messages
print_status() {
  echo -e "\033[1;34m$1\033[0m"  # Blue bold text
}

# Step 1: Ensure git-lfs is installed
print_status "Checking Git LFS installation..."
if ! command -v git-lfs &> /dev/null; then
  echo "Git LFS is not installed. Installing now..."
  sudo apt-get update && sudo apt-get install -y git-lfs
  if [[ $? -ne 0 ]]; then
    echo "Failed to install Git LFS. Please install it manually and re-run the script."
    exit 1
  fi
fi
git lfs install

# Step 2: Clone the Kokoro-82M repository
print_status "Cloning the Kokoro-82M repository..."
if [[ -d "$MODEL_DIR" ]]; then
  echo "Model directory '$MODEL_DIR' already exists. Skipping clone."
else
  git clone "$MODEL_REPO" "$MODEL_DIR"
  if [[ $? -ne 0 ]]; then
    echo "Failed to clone the repository. Please check your internet connection."
    exit 1
  fi
fi

# Step 3: Install system dependencies (espeak-ng)
print_status "Installing system dependencies..."
sudo apt-get update && sudo apt-get -qq -y install espeak-ng > /dev/null 2>&1
if [[ $? -ne 0 ]]; then
  echo "Failed to install system dependencies. Please check your permissions."
  exit 1
fi

# Step 4: Verify model and voicepack availability
print_status "Verifying model and voicepack availability..."
if [[ ! -f "$MODEL_DIR/kokoro-v0_19.pth" ]]; then
  echo "Model file 'kokoro-v0_19.pth' is missing in $MODEL_DIR."
  exit 1
fi

# Step 5: Display setup success
print_status "Model and dependencies are successfully set up!"
echo "Model directory: $MODEL_DIR"
echo "Voice directory: $VOICE_DIR"
