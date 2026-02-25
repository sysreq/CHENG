# CHENG — Shutdown dev servers (backend :8000, frontend :5173)

foreach ($port in @(8000, 5173)) {
    $procIds = netstat -ano | Select-String ":$port\s.*LISTENING" |
        ForEach-Object { ($_ -split '\s+')[-1] } | Sort-Object -Unique

    if ($procIds) {
        foreach ($p in $procIds) {
            Write-Host "Killing PID $p (port $port)"
            taskkill /F /PID $p 2>$null | Out-Null
        }
    } else {
        Write-Host "Nothing on port $port"
    }
}
