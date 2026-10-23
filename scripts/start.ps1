param([switch]$WithAsr, [switch]$WithPostgres, [int]$Port=8000)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $repo
try {
    if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
    }
    $extras = @('dev')
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
    & ./.venv/Scripts/python.exe -m services.launch --demo --port $Port
} finally { Pop-Location }
