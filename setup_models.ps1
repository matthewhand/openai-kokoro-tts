# setup_models.ps1
# Setup reproducible pinned Kokoro ONNX model and voices assets with SHA256 validation

$ErrorActionPreference = "Stop"

$MODEL_DIR = "models/kokoro"
if (-not (Test-Path $MODEL_DIR)) {
    New-Item -ItemType Directory -Force -Path $MODEL_DIR | Out-Null
}

$MODEL_FILE = Join-Path $MODEL_DIR "kokoro-v0_19.onnx"
$VOICES_FILE = Join-Path $MODEL_DIR "voices.json"

$MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx"
$VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.json"

$EXPECTED_MODEL_SHA256 = "dece567789190ebe987bd245d95c09d5ac86de28ff0c325c2e3faaf3de04442c"
$EXPECTED_VOICES_SHA256 = "ff3f0e5cf156088d4847f277e43c49e3248b798b47027d01afd75d78065744df"

function Test-FileHash {
    param (
        [string]$Path,
        [string]$ExpectedHash
    )
    if (Test-Path $Path) {
        $actual = (Get-FileHash -Algorithm SHA256 $Path).Hash.ToLower()
        return ($actual -eq $ExpectedHash.ToLower())
    }
    return $false
}

Write-Host "Setting up Kokoro ONNX model and voices assets in $MODEL_DIR..." -ForegroundColor Blue

if (Test-FileHash $VOICES_FILE $EXPECTED_VOICES_SHA256) {
    Write-Host "voices.json already present with valid SHA256."
} else {
    Write-Host "Downloading voices.json..."
    $tmpVoices = "$VOICES_FILE.tmp"
    Invoke-WebRequest -Uri $VOICES_URL -OutFile $tmpVoices -UseBasicParsing
    if (-not (Test-FileHash $tmpVoices $EXPECTED_VOICES_SHA256)) {
        Remove-Item -Force $tmpVoices
        Write-Error "voices.json SHA256 mismatch"
        exit 1
    }
    Move-Item -Force $tmpVoices $VOICES_FILE
    Write-Host "voices.json verified."
}

if (Test-FileHash $MODEL_FILE $EXPECTED_MODEL_SHA256) {
    Write-Host "kokoro-v0_19.onnx already present with valid SHA256."
} else {
    Write-Host "Downloading kokoro-v0_19.onnx..."
    $tmpModel = "$MODEL_FILE.tmp"
    Invoke-WebRequest -Uri $MODEL_URL -OutFile $tmpModel -UseBasicParsing
    if (-not (Test-FileHash $tmpModel $EXPECTED_MODEL_SHA256)) {
        Remove-Item -Force $tmpModel
        Write-Error "kokoro-v0_19.onnx SHA256 mismatch"
        exit 1
    }
    Move-Item -Force $tmpModel $MODEL_FILE
    Write-Host "kokoro-v0_19.onnx verified."
}

Write-Host "Kokoro ONNX CPU assets ready in $MODEL_DIR." -ForegroundColor Green