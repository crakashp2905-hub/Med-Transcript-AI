param([switch]$WithAsr, [switch]$WithPostgres, [int]$Port=8000, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $repo
try {
    $workspaceUrl = "http://127.0.0.1:$Port"
    $existingWorkspace = $false
    try {
        $health = Invoke-RestMethod "$workspaceUrl/health" -TimeoutSec 2
        $existingWorkspace = $health.status -eq 'ok'
    } catch { }
    if ($existingWorkspace) {
        Write-Host "Workspace already running: $workspaceUrl"
        if (Test-Path -LiteralPath 'data/local-config.json') {
            Write-Host ('Local access key: ' + ((Get-Content -Raw 'data/local-config.json' | ConvertFrom-Json).access_key))
        }
        if (-not $NoBrowser) { Start-Process $workspaceUrl }
        return
    }
    if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
    }
    $extras = @('dev','media')
    if ($WithAsr) { $extras += 'asr' }
    if ($WithPostgres) { $extras += 'postgres' }
    $installSpec = ".[" + ($extras -join ',') + "]"
    & ./.venv/Scripts/python.exe -m pip install -e $installSpec
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
    Push-Location apps/clinician-web
    try {
        npm ci
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    } finally { Pop-Location }
    $launchArgs = @('-m', 'services.launch', '--demo', '--port', "$Port")
    if (-not $NoBrowser) { $launchArgs += '--open' }
    & ./.venv/Scripts/python.exe @launchArgs
} finally { Pop-Location }
