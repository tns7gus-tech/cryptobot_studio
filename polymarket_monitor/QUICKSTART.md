# 🚀 빠른 실행 가이드

## 1️⃣ 자동 설정 (추천)

PowerShell에서 실행:
```powershell
.\setup.ps1
```

이 스크립트가 자동으로:
- ✅ Python 가상환경 생성
- ✅ 의존성 설치
- ✅ Playwright 브라우저 설치
- ✅ .env 파일 생성
- ✅ 필요한 디렉토리 생성

---

## 2️⃣ 필수 설정

### `.env` 파일 편집

```powershell
notepad .env
```

**반드시 설정해야 할 항목:**

```env
# Telegram Bot (필수)
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz  # @BotFather에서 발급
TELEGRAM_CHAT_ID=123456789  # @userinfobot에서 확인

# Google AI (필수)
GOOGLE_AI_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX  # Google AI Studio에서 발급

# Rotating Proxy (필수!)
PROXY_URL=http://proxy.provider.com:port
PROXY_USERNAME=your_username
PROXY_PASSWORD=your_password

# 타겟 위치 (쉼표로 구분)
TARGET_LOCATIONS=Domino's Pizza 2450 Crystal Dr Arlington VA,Pentagon City Pizza Hut,White House Area Restaurants
```

---

## 3️⃣ 실행

### 개발 모드 (테스트)

```powershell
# 가상환경 활성화
.\venv\Scripts\Activate.ps1

# 실행
python main.py
```

### 프로덕션 모드 (Docker)

```powershell
# Docker로 24/7 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f
```

---

## 4️⃣ 개별 모듈 테스트

실행 전에 각 모듈을 테스트하는 것을 추천합니다:

### Telegram 알림 테스트
```powershell
python telegram_notifier.py
```
→ Telegram으로 테스트 메시지가 와야 함

### Google Maps 스크래퍼 테스트
```powershell
python scraper.py
```
→ 콘솔에 스크래핑 결과 출력

### Polymarket 모니터 테스트
```powershell
python polymarket_monitor.py
```
→ 현재 마켓 목록 출력

---

## 5️⃣ 모니터링 확인

실행 후 다음을 확인하세요:

1. **Telegram 시작 메시지**
   - "✅ Polymarket Monitor Started" 메시지가 와야 함

2. **로그 파일**
   ```powershell
   Get-Content logs\polymarket_monitor_*.log -Wait
   ```

3. **알림 테스트**
   - 5분마다 스크래핑 실행
   - 이상 징후 발견 시 Telegram 알림

---

## 📊 예상 알림 예시

### Google Maps 알림
```
🚨 GOOGLE MAPS ALERT 🚨

📍 Location: Domino's Pizza (Pentagon City)
📊 Current Busyness: 85%
📈 Baseline: 30%
⚡ Delta: +55%

⚠️ Unusual activity detected!
```

### Polymarket 알림
```
🔴 POLYMARKET ALERT 🔴

📊 Market: Will there be US military action in 2024?

🎯 Current Probability: 5.0%
📉 Historical Average: 95.0%
⚡ Change: 90.0%

⚠️ POSSIBLE INSIDER TRADING PATTERN ⚠️
```

### 통합 알림 (두 신호 동시 발생)
```
🔥🔥🔥 COMBINED SIGNAL ALERT 🔥🔥🔥

BOTH INDICATORS TRIGGERED!

📍 Google Maps: Pentagon Pizza showing 85% busyness
📊 Polymarket: Military action probability dropped 90%

⚡ HIGH CONFIDENCE SIGNAL
🎯 ACTION RECOMMENDED
```

---

## ⚙️ 설정 조정

### 모니터링 주기 변경
```env
SCRAPE_INTERVAL_MINUTES=3  # 3분마다 (더 빠른 감지)
```

### 민감도 조정
```env
ANOMALY_THRESHOLD=30  # 30% 이상 변화 시 알림 (더 민감)
```

### 알림 시간대 변경
```env
ALERT_TIME_START=20:00  # 저녁 8시부터
ALERT_TIME_END=08:00    # 아침 8시까지
```

---

## 🛑 중지

### 개발 모드
```
Ctrl + C
```

### Docker 모드
```powershell
docker-compose down
```

---

## 🔧 문제 해결

### "ModuleNotFoundError"
```powershell
pip install -r requirements.txt
```

### "Playwright browser not found"
```powershell
playwright install chromium
```

### "Telegram error"
→ `.env` 파일의 `TELEGRAM_BOT_TOKEN`과 `TELEGRAM_CHAT_ID` 확인

### "Proxy connection failed"
→ 프록시 서비스 구독 및 설정 확인 (필수!)

---

## 📈 다음 단계

1. ✅ **1주일 데이터 수집**: 패턴 학습
2. 🤖 **Google AI 통합**: 고급 패턴 인식
3. 📊 **백테스팅**: 과거 데이터로 전략 검증
4. 🎯 **자동화**: 신호 발생 시 자동 베팅 (선택)

---

## 💡 팁

- **프록시는 필수**: Google은 스크래핑을 강력하게 차단
- **여러 위치 모니터링**: 더 많은 데이터 = 더 정확한 신호
- **시간대 주의**: 미국 동부 시간 기준으로 작동
- **법적 책임**: 모든 베팅은 본인 책임

---

## 📞 지원

문제가 발생하면:
1. `logs/` 디렉토리의 로그 파일 확인
2. 각 모듈을 개별적으로 테스트
3. `.env` 파일 설정 재확인
