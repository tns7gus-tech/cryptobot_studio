# Google Cloud Run Deployment Script
# Windows PowerShell

param(
    [string]$ProjectId = "",
    [string]$Region = "us-central1",
    [string]$ServiceName = "polymarket-whale-bot",
    [string]$Mode = "semi"  # semi or full
)

Write-Host "🚀 Polymarket Whale Bot - Cloud Run Deployment" -ForegroundColor Cyan
Write-Host ""

# Check if gcloud is installed
if (!(Get-Command gcloud -ErrorAction SilentlyContinue)) {
    Write-Host "❌ gcloud CLI not found!" -ForegroundColor Red
    Write-Host "Install from: https://cloud.google.com/sdk/docs/install" -ForegroundColor Yellow
    exit 1
}

# Get project ID if not provided
if ([string]::IsNullOrEmpty($ProjectId)) {
    $ProjectId = Read-Host "Enter your GCP Project ID"
}

Write-Host "📋 Configuration:" -ForegroundColor Yellow
Write-Host "  Project ID: $ProjectId"
Write-Host "  Region: $Region"
Write-Host "  Service: $ServiceName"
Write-Host "  Mode: $Mode"
Write-Host ""

# Set project
Write-Host "🔧 Setting GCP project..." -ForegroundColor Yellow
gcloud config set project $ProjectId

# Enable required APIs
Write-Host ""
Write-Host "🔧 Enabling required APIs..." -ForegroundColor Yellow
gcloud services enable run.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable cloudbuild.googleapis.com

# Create secrets (if they don't exist)
Write-Host ""
Write-Host "🔐 Setting up secrets..." -ForegroundColor Yellow

# Telegram Bot Token
if (Test-Path ".env") {
    $envContent = Get-Content ".env"
    
    # Extract values
    $telegramToken = ($envContent | Select-String "TELEGRAM_BOT_TOKEN=(.+)").Matches.Groups[1].Value
    $telegramChatId = ($envContent | Select-String "TELEGRAM_CHAT_ID=(.+)").Matches.Groups[1].Value
    $googleAiKey = ($envContent | Select-String "GOOGLE_AI_API_KEY=(.+)").Matches.Groups[1].Value
    
    if ($telegramToken) {
        Write-Host "  Creating telegram-bot-token secret..."
        echo $telegramToken | gcloud secrets create telegram-bot-token --data-file=- 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  Secret already exists, updating..." -ForegroundColor Yellow
            echo $telegramToken | gcloud secrets versions add telegram-bot-token --data-file=-
        }
    }
    
    if ($telegramChatId) {
        Write-Host "  Creating telegram-chat-id secret..."
        echo $telegramChatId | gcloud secrets create telegram-chat-id --data-file=- 2>$null
        if ($LASTEXITCODE -ne 0) {
            echo $telegramChatId | gcloud secrets versions add telegram-chat-id --data-file=-
        }
    }
    
    if ($googleAiKey) {
        Write-Host "  Creating google-ai-key secret..."
        echo $googleAiKey | gcloud secrets create google-ai-key --data-file=- 2>$null
        if ($LASTEXITCODE -ne 0) {
            echo $googleAiKey | gcloud secrets versions add google-ai-key --data-file=-
        }
    }
}

# For full auto mode, need private key
if ($Mode -eq "full") {
    Write-Host ""
    Write-Host "⚠️  FULL AUTO MODE requires Polymarket credentials" -ForegroundColor Yellow
    $privateKey = Read-Host "Enter Polymarket Private Key (or press Enter to skip)"
    $funderAddress = Read-Host "Enter Funder Address (or press Enter to skip)"
    
    if ($privateKey) {
        echo $privateKey | gcloud secrets create polymarket-private-key --data-file=- 2>$null
        if ($LASTEXITCODE -ne 0) {
            echo $privateKey | gcloud secrets versions add polymarket-private-key --data-file=-
        }
    }
    
    if ($funderAddress) {
        echo $funderAddress | gcloud secrets create polymarket-funder-address --data-file=- 2>$null
        if ($LASTEXITCODE -ne 0) {
            echo $funderAddress | gcloud secrets versions add polymarket-funder-address --data-file=-
        }
    }
}

# Build and deploy
Write-Host ""
Write-Host "🏗️  Building and deploying to Cloud Run..." -ForegroundColor Yellow

$deployArgs = @(
    "run", "deploy", $ServiceName,
    "--source", ".",
    "--platform", "managed",
    "--region", $Region,
    "--allow-unauthenticated",
    "--min-instances", "1",
    "--max-instances", "1",
    "--timeout", "3600",
    "--cpu", "1",
    "--memory", "512Mi",
    "--cpu-always-allocated",
    "--set-env-vars", "BOT_MODE=$Mode",
    "--set-secrets", "TELEGRAM_BOT_TOKEN=telegram-bot-token:latest",
    "--set-secrets", "TELEGRAM_CHAT_ID=telegram-chat-id:latest",
    "--set-secrets", "GOOGLE_AI_API_KEY=google-ai-key:latest"
)

if ($Mode -eq "full") {
    $deployArgs += "--set-secrets"
    $deployArgs += "POLYMARKET_PRIVATE_KEY=polymarket-private-key:latest"
    $deployArgs += "--set-secrets"
    $deployArgs += "POLYMARKET_FUNDER_ADDRESS=polymarket-funder-address:latest"
}

& gcloud $deployArgs

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Deployment successful!" -ForegroundColor Green
    Write-Host ""
    Write-Host "📊 View logs:" -ForegroundColor Cyan
    Write-Host "  gcloud run services logs tail $ServiceName --region=$Region"
    Write-Host ""
    Write-Host "🔍 View service:" -ForegroundColor Cyan
    Write-Host "  gcloud run services describe $ServiceName --region=$Region"
    Write-Host ""
    Write-Host "💰 Estimated cost: ~`$14/month" -ForegroundColor Yellow
    Write-Host ""
}
else {
    Write-Host ""
    Write-Host "❌ Deployment failed!" -ForegroundColor Red
    exit 1
}
