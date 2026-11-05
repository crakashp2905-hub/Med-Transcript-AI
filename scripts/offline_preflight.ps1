param([Parameter(Mandatory=$true)][string]$Out, [string]$OllamaRoot=$env:OLLAMA_MODELS)
$ErrorActionPreference='Stop'
$repoRoot=Split-Path -Parent $PSScriptRoot
$pythonPath=Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Cached project Python is unavailable. No installation was attempted.' }
Push-Location $repoRoot
try {
    if (-not $OllamaRoot) { $OllamaRoot=[Environment]::GetEnvironmentVariable('OLLAMA_MODELS','User') }
    $preflightArgs=@('scripts/offline_preflight','--out',$Out)
    if ($OllamaRoot) { $preflightArgs+=@('--ollama-root',$OllamaRoot) }
    & $pythonPath @preflightArgs
    if ($LASTEXITCODE -ne 0) { throw 'Offline preflight failed. Preserve earlier reports and inspect the failure.' }
} finally { Pop-Location }
