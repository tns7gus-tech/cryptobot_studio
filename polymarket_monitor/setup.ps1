# Polymarket Monitor - Quick Start Script
# Windows PowerShell

Write-Host "🚀 Polymarket Monitor - Quick Setup" -ForegroundColor Cyan
Write-Host ""

# Check Python
Write-Host "Checking Python installation..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Python not found! Please install Python 3.11+" -ForegroundColor Red
    exit 1
}
Write-Host "✅ $pythonVersion" -ForegroundColor Green

# Create virtual environment
Write-Host ""
Write-Host "Creating virtual environment..." -ForegroundColor Yellow
if (Test-Path "venv") {
    Write-Host "⚠️  Virtual environment already exists" -ForegroundColor Yellow
} else {
    python -m venv venv
    Write-Host "✅ Virtual environment created" -ForegroundColor Green
}

# Activate virtual environment
Write-Host ""
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

# Install dependencies
Write-Host ""
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

# Install Playwright
Write-Host ""
Write-Host "Installing Playwright browsers..." -ForegroundColor Yellow
playwright install chromium

# Create .env file
Write-Host ""
if (Test-Path ".env") {
    Write-Host "⚠️  .env file already exists" -ForegroundColor Yellow
} else {
    Write-Host "Creating .env file..." -ForegroundColor Yellow
    Copy-Item .env.example .env
    Write-Host "✅ .env file created" -ForegroundColor Green
    Write-Host ""
    Write-Host "⚠️  IMPORTANT: Edit .env file with your credentials!" -ForegroundColor Red
    Write-Host "   - TELEGRAM_BOT_TOKEN" -ForegroundColor Yellow
    Write-Host "   - TELEGRAM_CHAT_ID" -ForegroundColor Yellow
    Write-Host "   - GOOGLE_AI_API_KEY" -ForegroundColor Yellow
    Write-Host "   - PROXY_URL (필수!)" -ForegroundColor Yellow
    Write-Host ""
    
    $edit = Read-Host "Edit .env file now? (y/n)"
    if ($edit -eq "y") {
        notepad .env
    }
}

# Create directories
Write-Host ""
Write-Host "Creating directories..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "logs" | Out-Null
New-Item -ItemType Directory -Force -Path "data" | Out-Null
Write-Host "✅ Directories created" -ForegroundColor Green

# Test configuration
Write-Host ""
Write-Host "Testing configuration..." -ForegroundColor Yellow
$envExists = Test-Path ".env"
if ($envExists) {
    $envContent = Get-Content ".env"
    $hasToken = $envContent | Select-String "TELEGRAM_BOT_TOKEN=your_"
    $hasProxy = $envContent | Select-String "PROXY_URL=your_"
    
    if ($hasToken -or $hasProxy) {
        Write-Host "⚠️  WARNING: .env file contains placeholder values!" -ForegroundColor Red
        Write-Host "   Please edit .env file before running." -ForegroundColor Yellow
    } else {
        Write-Host "✅ Configuration looks good" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Setup complete! 🎉" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Edit .env file with your credentials" -ForegroundColor White
Write-Host "2. Run: python main.py" -ForegroundColor White
Write-Host ""
Write-Host "For testing individual modules:" -ForegroundColor Yellow
Write-Host "  python telegram_notifier.py  # Test Telegram" -ForegroundColor White
Write-Host "  python scraper.py            # Test Google Maps" -ForegroundColor White
Write-Host "  python polymarket_monitor.py # Test Polymarket" -ForegroundColor White
Write-Host ""
