# deploy-cheng.ps1 - Idiot-proof deployment script for CHENG to Google Cloud Run
# Usage: .\deploy-cheng.ps1 [-Project <id>] [-Region <region>] [-SkipBuild]

param(
    [string]$Project   = "cheng-488605",
    [string]$Region    = "us-central1",
    [string]$Service   = "cheng",
    [string]$Tag       = "latest",
    [switch]$SkipBuild
)

# If not running inside Windows Terminal, relaunch in a new wt window
if (-not $env:WT_SESSION) {
    $relaunchArgs = @()
    if ($SkipBuild) { $relaunchArgs += '-SkipBuild' }
    if ($Project -ne "cheng-488605") { $relaunchArgs += "-Project $Project" }
    if ($Region  -ne "us-central1")  { $relaunchArgs += "-Region $Region" }
    if ($Service -ne "cheng")        { $relaunchArgs += "-Service $Service" }
    if ($Tag     -ne "latest")       { $relaunchArgs += "-Tag $Tag" }
    $argStr = $relaunchArgs -join ' '
    wt -d "$PSScriptRoot" -- powershell.exe -ExecutionPolicy Bypass -File "$PSScriptRoot\deploy.ps1" $argStr
    exit
}

$ErrorActionPreference = "Stop"
$GCLOUD_BIN = "C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin"
$IMAGE = "$Region-docker.pkg.dev/$Project/cheng-images/$Service`:$Tag"
$GCLOUD_PATH_BASH = '/mnt/x/CHENG/gcloud-bin'

function Invoke-Bash {
    param([string]$Cmd)
    $full = 'export PATH="$PATH:' + $GCLOUD_PATH_BASH + '" && ' + $Cmd
    bash -c $full
    return $LASTEXITCODE
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  CHENG Cloud Run Deployment"               -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Project : $Project"
Write-Host "  Region  : $Region"
Write-Host "  Service : $Service"
Write-Host "  Image   : $IMAGE"
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# -- Step 0: Fix CRLF in deploy.sh --------------------------------------------
Write-Host "[0/4] Fixing line endings in deploy.sh..." -ForegroundColor Yellow
(Get-Content deploy.sh -Raw) -replace "`r`n", "`n" | Set-Content deploy.sh -NoNewline
Write-Host "      OK" -ForegroundColor Green

# -- Step 1: Start Docker Desktop if not running ------------------------------
Write-Host ""
Write-Host "[1/4] Checking Docker..." -ForegroundColor Yellow

$dockerRunning = $false
try { docker info 2>&1 | Out-Null; $dockerRunning = $true } catch {}

if (-not $dockerRunning) {
    Write-Host "      Docker not running - starting Docker Desktop..." -ForegroundColor Yellow

    $candidates = @(
        "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe",
        "${env:ProgramFiles(x86)}\Docker\Docker\Docker Desktop.exe"
    )
    $dockerExe = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $dockerExe) {
        Write-Host "ERROR: Docker Desktop not found. Please start it manually and re-run." -ForegroundColor Red
        exit 1
    }

    Start-Process $dockerExe
    Write-Host "      Waiting for Docker to become ready (this may take ~30s)..." -ForegroundColor Yellow

    $timeout = 120
    $elapsed = 0
    while ($elapsed -lt $timeout) {
        Start-Sleep 5
        $elapsed += 5
        try { docker info 2>&1 | Out-Null; $dockerRunning = $true; break } catch {}
        Write-Host "      Still waiting... ($elapsed s)" -ForegroundColor DarkGray
    }

    if (-not $dockerRunning) {
        Write-Host "ERROR: Docker did not start within $timeout seconds. Please start it manually." -ForegroundColor Red
        exit 1
    }
}
Write-Host "      Docker is running." -ForegroundColor Green

# -- Step 2: Ensure gcloud auth in bash ---------------------------------------
Write-Host ""
Write-Host "[2/4] Checking gcloud authentication..." -ForegroundColor Yellow

$authCheck = Invoke-Bash "gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null"
if ([string]::IsNullOrWhiteSpace($authCheck)) {
    Write-Host "      Not authenticated - starting login..." -ForegroundColor Yellow
    Invoke-Bash "gcloud auth login --no-launch-browser"
    Invoke-Bash "gcloud config set project $Project"
    Invoke-Bash "gcloud auth configure-docker $Region-docker.pkg.dev"
} else {
    Write-Host "      Authenticated as: $authCheck" -ForegroundColor Green
}

# -- Step 3: Build + Push -----------------------------------------------------
if (-not $SkipBuild) {
    Write-Host ""
    Write-Host "[3/4] Building Docker image..." -ForegroundColor Yellow
    docker build --target runtime --tag $IMAGE .
    if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: Docker build failed." -ForegroundColor Red; exit 1 }
    Write-Host "      Build complete." -ForegroundColor Green

    Write-Host ""
    Write-Host "      Pushing image to Artifact Registry..." -ForegroundColor Yellow
    $env:PATH += ";$GCLOUD_BIN"
    docker push $IMAGE
    if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: Docker push failed." -ForegroundColor Red; exit 1 }
    Write-Host "      Push complete." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[3/4] Skipping build and push (-SkipBuild)" -ForegroundColor DarkGray
}

# -- Step 4: Deploy to Cloud Run ----------------------------------------------
Write-Host ""
Write-Host "[4/4] Deploying to Cloud Run..." -ForegroundColor Yellow

$deployCmd = "gcloud run deploy $Service" +
    " --image $IMAGE" +
    " --region $Region" +
    " --project $Project" +
    " --platform managed" +
    " --memory 2Gi" +
    " --cpu 2" +
    " --min-instances 1" +
    " --max-instances 10" +
    " --concurrency 4" +
    " --timeout 3600" +
    " --set-env-vars CHENG_MODE=cloud" +
    " --allow-unauthenticated" +
    " --port 8080"

$rc = Invoke-Bash $deployCmd
if ($rc -ne 0) { Write-Host "ERROR: Cloud Run deployment failed." -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Deployment complete!" -ForegroundColor Green
Write-Host "  Service URL:" -ForegroundColor Cyan
Invoke-Bash "gcloud run services describe $Service --region $Region --project $Project --format 'value(status.url)'"
Write-Host "============================================" -ForegroundColor Cyan
