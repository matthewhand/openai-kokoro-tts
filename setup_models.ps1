# setup_models.ps1
# Download the pinned Kokoro v0.19 ONNX model + voices.json (the pair expected by
# kokoro-onnx 0.2.6, see MODELS.md) into .\models\kokoro, verifying exact size and
# SHA-256. Idempotent: a file that already matches is left alone.
# Mirrors setup_models.sh - keep the two in sync.

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
# The default progress bar makes Invoke-WebRequest of a ~325 MB file extremely slow in Windows PowerShell 5.1.
$ProgressPreference = "SilentlyContinue"

# Always operate relative to the repo root (where docker-compose.yml mounts ./models).
Set-Location -LiteralPath $PSScriptRoot

$MODEL_DIR = Join-Path "models" "kokoro"
$BASE_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1"

$MODEL_NAME = "kokoro-v1.0.onnx"
$MODEL_SIZE = 325505369
$MODEL_SHA256 = "beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a"

$VOICES_NAME = "voices-v1.0.bin"
$VOICES_SIZE = 28214398
$VOICES_SHA256 = "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d"

# $true if $Path exists with exactly $Size bytes and SHA-256 $Sha256.
function Test-Asset {
    param([string]$Path, [long]$Size, [string]$Sha256)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }
    if ((Get-Item -LiteralPath $Path).Length -ne $Size) { return $false }
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
    return ($actual -eq $Sha256.ToLowerInvariant())
}

function Get-Asset {
    param([string]$Name, [long]$Size, [string]$Sha256)
    $dest = Join-Path $MODEL_DIR $Name
    $tmp = "$dest.tmp"

    if (Test-Asset $dest $Size $Sha256) {
        Write-Host "$Name already present (size and SHA-256 OK)."
        return
    }

    Write-Host "Downloading $Name ($Size bytes)..."
    try {
        if (Test-Path -LiteralPath $tmp) { Remove-Item -Force -LiteralPath $tmp }  # partial file from an interrupted run
        Invoke-WebRequest -Uri "$BASE_URL/$Name" -OutFile $tmp -UseBasicParsing

        $actualSize = (Get-Item -LiteralPath $tmp).Length
        if ($actualSize -ne $Size) {
            throw "$Name size mismatch (expected $Size, got $actualSize)"
        }
        $actualSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $tmp).Hash.ToLowerInvariant()
        if ($actualSha -ne $Sha256.ToLowerInvariant()) {
            throw "$Name SHA-256 mismatch (expected $Sha256, got $actualSha)"
        }
        Move-Item -Force -LiteralPath $tmp -Destination $dest
        Write-Host "$Name verified."
    }
    finally {
        # Runs on success (nothing left), failure, and Ctrl+C: never leave a partial/unverified file behind.
        if (Test-Path -LiteralPath $tmp) { Remove-Item -Force -LiteralPath $tmp -ErrorAction SilentlyContinue }
    }
}

Write-Host "Setting up Kokoro ONNX model and voices assets in $MODEL_DIR..." -ForegroundColor Blue
New-Item -ItemType Directory -Force -Path $MODEL_DIR | Out-Null

Get-Asset $VOICES_NAME $VOICES_SIZE $VOICES_SHA256
Get-Asset $MODEL_NAME $MODEL_SIZE $MODEL_SHA256

Write-Host "Kokoro ONNX CPU assets ready in $MODEL_DIR." -ForegroundColor Green
