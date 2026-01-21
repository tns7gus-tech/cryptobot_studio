# Polymarket Monitor - 설정 가이드

## 📋 필수 준비사항

### 1. Telegram Bot 생성
1. Telegram에서 [@BotFather](https://t.me/botfather) 검색
2. `/newbot` 명령어 입력
3. 봇 이름 설정 (예: Polymarket Alert Bot)
4. 봇 사용자명 설정 (예: polymarket_alert_bot)
5. **API Token 복사** → `.env` 파일의 `TELEGRAM_BOT_TOKEN`에 입력

### 2. Telegram Chat ID 확인
1. [@userinfobot](https://t.me/userinfobot) 검색
2. 봇과 대화 시작
3. **Chat ID 복사** → `.env` 파일의 `TELEGRAM_CHAT_ID`에 입력

### 3. Google AI API Key
1. [Google AI Studio](https://makersuite.google.com/app/apikey) 접속
2. "Create API Key" 클릭
3. **API Key 복사** → `.env` 파일의 `GOOGLE_AI_API_KEY`에 입력

### 4. Rotating Proxy (필수!)
Google은 스크래핑을 강력하게 차단하므로 **미국 주거용 IP 프록시**가 필수입니다.

#### 추천 프록시 서비스:
- **Bright Data** (구 Luminati): https://brightdata.com
- **Smartproxy**: https://smartproxy.com
- **Oxylabs**: https://oxylabs.io

#### 프록시 설정:
```env
PROXY_URL=http://proxy.provider.com:port
PROXY_USERNAME=your_username
PROXY_PASSWORD=your_password
```

---

## 🚀 설치 및 실행

### Windows (PowerShell)

```powershell
# 1. Python 가상환경 생성
python -m venv venv

# 2. 가상환경 활성화
.\venv\Scripts\Activate.ps1

# 3. 의존성 설치
pip install -r requirements.txt

# 4. Playwright 브라우저 설치
playwright install chromium

# 5. .env 파일 생성
Copy-Item .env.example .env

# 6. .env 파일 편집 (메모장으로)
notepad .env

# 7. 실행
python main.py
```

### Linux/Mac

```bash
# 1. Python 가상환경 생성
python3 -m venv venv

# 2. 가상환경 활성화
source venv/bin/activate

# 3. 의존성 설치
pip install -r requirements.txt

# 4. Playwright 브라우저 설치
playwright install chromium

# 5. .env 파일 생성
cp .env.example .env

# 6. .env 파일 편집
nano .env

# 7. 실행
python main.py
```

---

## 🎯 타겟 위치 설정

`.env` 파일의 `TARGET_LOCATIONS`에 모니터링할 장소를 설정:

```env
TARGET_LOCATIONS=Domino's Pizza 2450 Crystal Dr Arlington VA,Pentagon City Pizza Hut,White House Area Waffle House,CIA Headquarters Nearby Restaurants
```

### 추천 타겟 위치:

#### 펜타곤 인근:
- `Domino's Pizza 2450 Crystal Dr Arlington VA`
- `Pentagon City Pizza Hut`
- `Crystal City Restaurants`

#### 백악관 인근:
- `White House Area Pizza Restaurants`
- `Downtown DC Waffle House`
- `K Street Bars and Restaurants`

#### CIA 본부 인근:
- `Langley VA Restaurants`
- `McLean VA Pizza Delivery`

---

## ⚙️ 설정 파라미터

### 모니터링 주기
```env
SCRAPE_INTERVAL_MINUTES=5  # 5분마다 체크
```

### 이상 징후 임계값
```env
ANOMALY_THRESHOLD=50  # 평소보다 50% 이상 혼잡할 때 알림
```

### 알림 시간대
```env
ALERT_TIME_START=22:00  # 밤 10시부터
ALERT_TIME_END=06:00    # 아침 6시까지
```

---

## 🐳 Docker로 24/7 실행

### 1. Docker 설치
- Windows: [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Linux: `sudo apt install docker.io docker-compose`

### 2. 실행
```bash
# 빌드 및 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 중지
docker-compose down
```

---

## 🔍 테스트

각 모듈을 개별적으로 테스트할 수 있습니다:

```bash
# Google Maps 스크래퍼 테스트
python scraper.py

# Polymarket 모니터 테스트
python polymarket_monitor.py

# Telegram 알림 테스트
python telegram_notifier.py
```

---

## 📊 로그 확인

로그는 `logs/` 디렉토리에 저장됩니다:

```bash
# 실시간 로그 확인 (Windows)
Get-Content logs\polymarket_monitor_*.log -Wait

# 실시간 로그 확인 (Linux/Mac)
tail -f logs/polymarket_monitor_*.log
```

---

## ⚠️ 주의사항

1. **프록시 필수**: 프록시 없이 실행하면 Google에서 IP 차단됨
2. **API 제한**: Google AI API는 무료 티어에서 분당 요청 제한 있음
3. **법적 책임**: Polymarket 베팅은 본인 책임
4. **ToS 위반**: Google Maps 스크래핑은 서비스 약관 위반 가능성 있음

---

## 🆘 문제 해결

### "Telegram bot token is invalid"
→ `.env` 파일의 `TELEGRAM_BOT_TOKEN` 확인

### "Failed to connect to proxy"
→ 프록시 URL, 사용자명, 비밀번호 확인

### "No target locations configured"
→ `.env` 파일의 `TARGET_LOCATIONS` 설정 확인

### "Playwright browser not found"
→ `playwright install chromium` 실행

---

## 📈 다음 단계

1. ✅ 기본 모니터링 시작
2. 🔄 데이터 수집 및 패턴 분석
3. 🤖 Google AI로 고급 패턴 인식 추가
4. 📊 백테스팅 시스템 구축
5. 🎯 자동 베팅 시스템 (선택사항)
