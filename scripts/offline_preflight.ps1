param([Parameter(Mandatory=$true)][string]$Out)
$ErrorActionPreference='Stop'
$repoRoot=Split-Path -Parent $PSScriptRoot
$pythonPath=Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Cached project Python is unavailable. No installation was attempted.' }
Push-Location $repoRoot
try {
    & $pythonPath scripts/offline_preflight --out $Out
    if ($LASTEXITCODE -ne 0) { throw 'Offline preflight failed. Preserve earlier reports and inspect the failure.' }
} finally { Pop-Location }
