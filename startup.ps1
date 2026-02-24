# CHENG — Start dev servers (backend :8000, frontend :5173)
param(
    [Alias('r')]
    [switch]$Reload
)

# Kill existing servers if running
$existing = netstat -ano | Select-String ":(8000|5173)\s.*LISTENING"
if ($existing) {
    Write-Host "Shutting down existing servers..."
    & "$PSScriptRoot\shutdown.ps1"
    Start-Sleep -Seconds 1
}

# Build frontend
Write-Host "Building frontend..."
Push-Location frontend
pnpm install --frozen-lockfile 2>$null
$buildResult = pnpm build 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Frontend build failed:" -ForegroundColor Red
    Write-Host $buildResult
    Pop-Location
    exit 1
}
Write-Host "Frontend built." -ForegroundColor Green
Pop-Location

# Start backend
$uvicornArgs = "backend.main:app --host 0.0.0.0 --port 8000"
if ($Reload) {
    $uvicornArgs += " --reload"
    Write-Host "Starting backend (with --reload)..."
} else {
    Write-Host "Starting backend..."
}
Start-Process -NoNewWindow -FilePath "uvicorn" -ArgumentList $uvicornArgs

# Start frontend dev server
Write-Host "Starting frontend dev server..."
Start-Process -NoNewWindow -FilePath "cmd" -ArgumentList "/c cd frontend && pnpm dev"

Start-Sleep -Seconds 3
Write-Host ""
Write-Host "Backend:  http://localhost:8000" -ForegroundColor Cyan
Write-Host "Frontend: http://localhost:5173" -ForegroundColor Cyan
if ($Reload) {
    Write-Host "(backend auto-reload enabled)" -ForegroundColor Yellow
}
