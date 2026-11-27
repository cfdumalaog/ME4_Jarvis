param(
    [string]$SecretFile = '',
    [string]$QwenBaseUrl = 'http://202.92.159.240:8000/v1',
    [string]$QwenModel = 'Qwen/Qwen3.8-27B',
    [switch]$SkipConfigure
)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$workspaceRoot = (Resolve-Path (Join-Path $repoRoot '..\..')).Path
$python = Join-Path $workspaceRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Shared workspace Python was not found at $python"
}

if ([string]::IsNullOrWhiteSpace($SecretFile)) {
    $SecretFile = Join-Path $workspaceRoot 'AI 231\Dumalaog_ME3 - Voice Duplex\secrets.txt'
}

# Read the protected handoff only in memory. Never write or echo these values.
$qwenKey = $env:QWEN_TEXT_API_KEY
if ([string]::IsNullOrWhiteSpace($qwenKey) -and (Test-Path -LiteralPath $SecretFile -PathType Leaf)) {
    foreach ($line in [IO.File]::ReadAllLines($SecretFile)) {
        if ($line -match '(?i)Qwen\s*3\.6.*?\bkey\s+(.+?)\s*$') {
            $candidate = $Matches[1].Trim().Trim('`"''')
            if (-not [string]::IsNullOrWhiteSpace($candidate)) {
                $qwenKey = $candidate
                break
            }
        }
    }
}
if ([string]::IsNullOrWhiteSpace($qwenKey)) {
    throw 'Qwen 3.6 credential was not found in the protected secret file or process environment.'
}

$env:QWEN_TEXT_API_KEY = $qwenKey
$env:VLLM_API_KEY = $qwenKey
$env:QWEN_TEXT_BASE_URL = $QwenBaseUrl
$env:QWEN_TEXT_MODEL = $QwenModel

# Audio credentials are intentionally process-only as well. The text key is
# not silently reused: ASR/TTS are served by a separate protected vLLM
# instance. The launcher accepts an environment seed or the sentence-form
# audio key in the protected handoff file; both adapters receive the same
# process-scoped value.
$audioKey = $env:QWEN_AUDIO_API_KEY
if ([string]::IsNullOrWhiteSpace($audioKey)) { $audioKey = $env:QWEN_INSTRUCT_API_KEY }
if ([string]::IsNullOrWhiteSpace($audioKey) -and (Test-Path -LiteralPath $SecretFile -PathType Leaf)) {
    foreach ($line in [IO.File]::ReadAllLines($SecretFile)) {
        # The supplied handoff uses a sentence rather than KEY=value:
        # "The API Key for both models is ...". Keep the value process-only.
        if ($line -match '(?i)API\s+Key\s+for\s+both\s+models\s+is\s+(.+?)\s*$') {
            $candidate = $Matches[1].Trim().Trim('`"''')
            if (-not [string]::IsNullOrWhiteSpace($candidate)) {
                $audioKey = $candidate
                break
            }
        }
    }
}
if (-not [string]::IsNullOrWhiteSpace($audioKey)) {
    $env:QWEN_AUDIO_API_KEY = $audioKey
    $env:QWEN_INSTRUCT_API_KEY = $audioKey
}

if (-not $SkipConfigure) {
    & $python (Join-Path $repoRoot 'scripts\configure_qwen.py')
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Push-Location $repoRoot
try {
    & $python 'main.py'
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
