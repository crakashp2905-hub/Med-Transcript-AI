param([Parameter(Mandatory=$true)][string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$segments = @(
    @{role='patient';text='I have had a cough for three days, but no fever.'},
    @{role='patient';text='I take metformin, but I am not sure whether the tablet is five hundred or eight hundred and fifty milligrams.'},
    @{role='clinician';text='Please bring the medication label so we can confirm the strength before completing the medication record.'},
    @{role='patient';text='I have no known drug allergies.'},
    @{role='clinician';text='We discussed returning for review if symptoms persist.'}
)
$format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
for ($i=0; $i -lt $segments.Count; $i++) {
    $voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
    try {
        $voice.SetOutputToWaveFile((Join-Path $OutputDirectory "$i.wav"), $format)
        $voice.Speak($segments[$i].text)
    } finally { $voice.Dispose() }
}
$segments | ConvertTo-Json | Set-Content -Encoding utf8 -LiteralPath (Join-Path $OutputDirectory 'segments.json')
