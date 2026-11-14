param(
    [Parameter(Mandatory=$true)][string]$Image,
    [string[]]$Tests = @('tests/test_offline_engineering.py', 'tests/test_domain_integrity.py')
)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

# This runner never builds or pulls an image. Provision the image and test
# dependencies before the isolated run, then bind the checked-out source read-only.
& docker image inspect $Image *> $null
if ($LASTEXITCODE -ne 0) {
    throw 'The requested offline test image is not present locally; no pull/build was attempted.'
}
if (-not $Tests -or $Tests.Count -eq 0) {
    throw 'At least one test path is required.'
}

$dockerArgs = @(
    'run', '--rm', '--network', 'none', '--read-only',
    '--tmpfs', '/tmp:rw,noexec,nosuid,size=1g',
    '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
    '--pids-limit', '128', '--memory', '4g',
    '--volume', "${repoRoot}:/workspace:ro", '--workdir', '/workspace',
    '--env', 'MED_TRANSCRIPT_OFFLINE=1', $Image,
    'python', '-m', 'services.safe_pytest'
)
$dockerArgs += $Tests
& docker @dockerArgs
if ($LASTEXITCODE -ne 0) {
    throw "Egress-denied test run failed with exit code $LASTEXITCODE."
}
