# setup_models.ps1
# Variables for model and voice directories
$MODEL_REPO = "https://huggingface.co/hexgrad/Kokoro-82M"
$MODEL_DIR = "models/kokoro"
$VOICE_DIR = "voices"
$VOICES_JSON_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.json"

function Print-Status {
    param (
        [string]$Message
    )
    Write-Host $Message -ForegroundColor Blue
}

# Step 1: Ensure Git LFS is installed
Print-Status "Checking Git LFS installation..."
if (-not (Get-Command git-lfs -ErrorAction SilentlyContinue)) {
    Write-Host "Git LFS is not installed. Installing now..."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install --id Git.LFS -e
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Error: Failed to install Git LFS. Please install it manually and re-run the script."
            exit 1
        }
    } elseif (Get-Command choco -ErrorAction SilentlyContinue) {
        choco install git-lfs -y
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Error: Failed to install Git LFS via Chocolatey. Please install it manually and re-run the script."
            exit 1
        }
    } else {
        Write-Host "Error: Neither winget nor Chocolatey is available for auto-installing Git LFS. Please install Git LFS manually."
        exit 1
    }
}
git lfs install

# Step 2: Clone the Kokoro-82M model repository
Print-Status "Cloning the Kokoro-82M repository..."
if (Test-Path $MODEL_DIR) {
    Write-Host "Model directory '$MODEL_DIR' already exists. Skipping clone."
} else {
    git clone $MODEL_REPO $MODEL_DIR
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Failed to clone the Kokoro model repository. Check your internet connection and try again."
        exit 1
    }
}

# Step 3: Install required system dependencies (espeak-ng)
Print-Status "Installing system dependencies..."
if (Get-Command winget -ErrorAction SilentlyContinue) {
    winget install --id espeak-ng -e --silent
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Failed to install espeak-ng using winget. Check your permissions or package manager configuration."
        exit 1
    }
} elseif (Get-Command choco -ErrorAction SilentlyContinue) {
    choco install espeak-ng -y
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Failed to install espeak-ng via Chocolatey. Check your permissions or package manager configuration."
        exit 1
    }
} else {
    Write-Host "Error: Neither winget nor Chocolatey is available for auto-installing espeak-ng. Please install espeak-ng manually."
    exit 1
}

# Step 4: Verify the model file exists and convert to ONNX
Print-Status "Verifying model file availability and converting to ONNX..."
if (-not (Test-Path "$MODEL_DIR\kokoro-v0_19.pth")) {
    Write-Host "Error: Model file 'kokoro-v0_19.pth' is missing in $MODEL_DIR."
    exit 1
}

# Install Python dependencies
pip install torch onnxruntime

# Run the conversion script
python openai_kokoro_tts/convert_to_onnx.py

if (-not (Test-Path "$MODEL_DIR\kokoro-v0_19.onnx")) {
    Write-Host "Error: Model file 'kokoro-v0_19.onnx' is missing in $MODEL_DIR."
    exit 1
}

# Step 5: Download voices.json
Print-Status "Downloading voices.json configuration..."
try {
    Invoke-WebRequest -Uri $VOICES_JSON_URL -OutFile "$MODEL_DIR\voices.json" -UseBasicParsing -ErrorAction Stop
} catch {
    Write-Host "Error: Failed to download voices.json. Check your internet connection and try again."
    exit 1
}

# Step 6: Display setup success
Print-Status "Model and dependencies have been successfully set up!"
Write-Host "Model directory: $MODEL_DIR"
Write-Host "Voice directory: $VOICE_DIR"