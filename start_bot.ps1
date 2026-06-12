param(
    [switch]$RunBotInWsl,
    [switch]$RunVk
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Read-DotEnvValue {
    param([string]$Name, [string]$Default = "")

    if (-not (Test-Path ".env")) {
        return $Default
    }

    $line = Get-Content ".env" | Where-Object { $_ -match "^\s*$Name\s*=" } | Select-Object -First 1
    if (-not $line) {
        return $Default
    }

    return ($line -replace "^\s*$Name\s*=\s*", "").Trim().Trim('"').Trim("'")
}

function Test-OllamaApi {
    param([string]$Url)

    try {
        Invoke-RestMethod -Uri "$Url/api/tags" -TimeoutSec 2 | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Wait-Ollama {
    param([string]$Url)

    for ($i = 0; $i -lt 30; $i++) {
        if (Test-OllamaApi -Url $Url) {
            return
        }
        Start-Sleep -Seconds 1
    }

    throw "Ollama API is not reachable at $Url"
}

function Start-OllamaWindows {
    param([string]$Url)

    $ollama = Get-Command "ollama" -ErrorAction SilentlyContinue
    if (-not $ollama) {
        return $false
    }

    if (-not (Test-OllamaApi -Url $Url)) {
        Write-Host "Starting Ollama for Windows..."
        Start-Process -FilePath $ollama.Source -ArgumentList "serve" -WindowStyle Hidden
        Wait-Ollama -Url $Url
    }

    return $true
}

function Start-OllamaWsl {
    param([string]$Url)

    $wsl = Get-Command "wsl" -ErrorAction SilentlyContinue
    if (-not $wsl) {
        return $false
    }

    $hasOllama = & wsl bash -lc "command -v ollama >/dev/null 2>&1; echo `$?"
    if ($hasOllama.Trim() -ne "0") {
        return $false
    }

    if (-not (Test-OllamaApi -Url $Url)) {
        Write-Host "Starting Ollama in WSL..."
        & wsl bash -lc "pgrep -f 'ollama serve' >/dev/null || (nohup ollama serve > ~/.ollama/serve.log 2>&1 &)"
        Wait-Ollama -Url $Url
    }

    return $true
}

function Ensure-OllamaModel {
    param(
        [string]$Model,
        [bool]$UseWsl
    )

    Write-Host "Checking Ollama model: $Model"
    if ($UseWsl) {
        $models = & wsl ollama list
        if ($models -notmatch [regex]::Escape($Model)) {
            Write-Host "Pulling model in WSL: $Model"
            & wsl ollama pull $Model
        }
    }
    else {
        $models = & ollama list
        if ($models -notmatch [regex]::Escape($Model)) {
            Write-Host "Pulling model: $Model"
            & ollama pull $Model
        }
    }
}

function Warm-OllamaModel {
    param([string]$Url, [string]$Model)

    Write-Host "Warming model: $Model"
    $body = @{
        model = $Model
        prompt = "ok"
        stream = $false
        options = @{
            num_predict = 1
        }
    } | ConvertTo-Json -Depth 5

    try {
        Invoke-RestMethod -Uri "$Url/api/generate" -Method Post -ContentType "application/json" -Body $body -TimeoutSec 120 | Out-Null
    }
    catch {
        Write-Host "Model warm-up failed, but bot can still start: $($_.Exception.Message)"
    }
}

function Convert-ToWslPath {
    param([string]$WindowsPath)

    $full = (Resolve-Path $WindowsPath).Path
    if ($full -match "^([A-Za-z]):\\(.*)$") {
        $drive = $matches[1].ToLower()
        $rest = $matches[2] -replace "\\", "/"
        return "/mnt/$drive/$rest"
    }

    throw "Cannot convert path to WSL: $WindowsPath"
}

function Start-BotWindows {
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        Write-Host "Creating Windows virtual environment..."
        python -m venv .venv
    }

    Write-Host "Installing Python dependencies..."
    & ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt

    if ($RunVk) {
        Write-Host "Starting VK bot..."
        & ".\.venv\Scripts\python.exe" vk_bot.py
    }
    else {
        Write-Host "Starting Telegram bot..."
        & ".\.venv\Scripts\python.exe" bot.py
    }
}

function Start-BotWsl {
    $wslPath = Convert-ToWslPath -WindowsPath $PSScriptRoot
    $entrypoint = "bot.py"
    if ($RunVk) {
        $entrypoint = "vk_bot.py"
    }

    $command = @"
cd '$wslPath' &&
if [ -d .venv-wsl ] && [ ! -f .venv-wsl/bin/activate ]; then rm -rf .venv-wsl; fi &&
if [ ! -d .venv-wsl ]; then python3 -m venv .venv-wsl; fi &&
. .venv-wsl/bin/activate &&
pip install -r requirements.txt &&
python $entrypoint
"@

    if ($RunVk) {
        Write-Host "Starting VK bot in WSL..."
    }
    else {
        Write-Host "Starting Telegram bot in WSL..."
    }
    & wsl bash -lc $command
}

if (-not (Test-Path ".env")) {
    throw "Missing .env. Copy .env.example to .env and fill TELEGRAM_BOT_TOKEN."
}

$ollamaUrl = Read-DotEnvValue -Name "OLLAMA_URL" -Default "http://127.0.0.1:11434"
$ollamaModel = Read-DotEnvValue -Name "OLLAMA_MODEL" -Default "llama3.2:3b"

$usingWslOllama = $false
if (-not (Start-OllamaWindows -Url $ollamaUrl)) {
    $usingWslOllama = Start-OllamaWsl -Url $ollamaUrl
}

if (-not (Test-OllamaApi -Url $ollamaUrl)) {
    throw "Could not start Ollama. Install Ollama for Windows or make sure it works in WSL."
}

Ensure-OllamaModel -Model $ollamaModel -UseWsl:$usingWslOllama
Warm-OllamaModel -Url $ollamaUrl -Model $ollamaModel

if ($RunBotInWsl) {
    Start-BotWsl
}
else {
    Start-BotWindows
}
