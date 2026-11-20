param(
    [Parameter(Mandatory=$true)][string]$OutputPath,
    [Parameter(Mandatory=$true)][string]$Text
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Add-Type -AssemblyName System.Speech

$repoRoot = [System.IO.Path]::GetFullPath((Get-Location).Path)
$resolvedOutput = [System.IO.Path]::GetFullPath($OutputPath)
$prefix = $repoRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
if (-not $resolvedOutput.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'OutputPath must stay inside the repository.'
}
if (Test-Path -LiteralPath $resolvedOutput) {
    throw 'OutputPath already exists.'
}

$directory = Split-Path -Parent $resolvedOutput
New-Item -ItemType Directory -Force -Path $directory | Out-Null
$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $voice.SelectVoice('Microsoft Zira Desktop')
    $voice.Rate = 0
    $voice.Volume = 100
    $format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(
        16000,
        [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,
        [System.Speech.AudioFormat.AudioChannel]::Mono
    )
    $voice.SetOutputToWaveFile($resolvedOutput, $format)
    $voice.Speak($Text)
    $voice.SetOutputToNull()
    [pscustomobject]@{
        engine = 'Windows System.Speech'
        voice = 'Microsoft Zira Desktop'
        culture = 'en-US'
        rate = 0
        volume = 100
        sample_rate = 16000
        channels = 1
        sample_width_bits = 16
    } | ConvertTo-Json -Compress
} finally {
    $voice.Dispose()
}
