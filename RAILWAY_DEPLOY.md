# Railway 배포 가이드 - CryptoBot Studio

Railway는 GitHub 연동으로 간편하게 배포할 수 있는 클라우드 플랫폼입니다.

---

## 📋 사전 준비 (완료됨)

- ✅ `Dockerfile` - 컨테이너 빌드 설정
- ✅ `railway.json` - Railway 배포 설정  
- ✅ `requirements.txt` - Python 패키지 목록
- ✅ `.env` 파일에 환경변수 설정됨

---

## 🚀 배포 순서

### Step 1. GitHub에 코드 푸시

프로젝트가 GitHub 리포지토리에 없다면 먼저 푸시:

```bash
cd d:/projects/cryptobot_studio
git init
git add .
git commit -m "Initial commit: CryptoBot Studio"
git remote add origin https://github.com/YOUR_USERNAME/cryptobot_studio.git
git push -u origin main
```

> ⚠️ `.env` 파일은 `.gitignore`에 포함되어 있어 푸시되지 않습니다 (보안상 정상)

---

### Step 2. Railway 가입

1. [https://railway.app](https://railway.app) 접속
2. **"Start a New Project"** 또는 **"Login"** 클릭
3. **GitHub으로 로그인** 선택 (가장 편함)

---

### Step 3. 새 프로젝트 생성

1. 대시보드에서 **"New Project"** 클릭
2. **"Deploy from GitHub repo"** 선택
3. GitHub 리포지토리 목록에서 **`cryptobot_studio`** 선택
4. Railway가 자동으로 Dockerfile을 감지하고 빌드 시작

---

### Step 4. 환경변수 설정 (중요!)

Railway 대시보드에서:

1. 프로젝트 클릭 → **"Variables"** 탭 선택
2. **"Add Variable"** 또는 **"RAW Editor"** 클릭
3. 아래 환경변수 추가:

```
TELEGRAM_BOT_TOKEN=6650752059:AAHARLi1YWBCZS6UtUAd3m878e1pVsBWwiM
TELEGRAM_CHAT_ID=1758292808
UPBIT_ACCESS_KEY=lDRmkdQ51Lx2TkzoBWKNLVweg9Ker96ohzJWnd0W
UPBIT_SECRET_KEY=b0yhqHzApMxxn0tYG5jHC65xBNFfpyebwPnP2yzZ
TRADE_SYMBOL=KRW-ETH
TRADE_AMOUNT=10000
BB_PERIOD=20
BB_STD=2
MAX_DAILY_TRADES=10
MAX_DAILY_LOSS=50000
BOT_MODE=full
LOG_LEVEL=INFO
PORT=8080
```

> 💡 **RAW Editor**를 사용하면 한 번에 붙여넣기 가능!

---

### Step 5. 배포 확인

1. **"Deployments"** 탭에서 빌드 로그 확인
2. 성공 시 **"View Logs"**에서 봇 실행 로그 확인
3. Telegram에서 시작 알림 메시지 수신 확인

---

## 🔧 유용한 기능

### 로그 확인
- Railway 대시보드 → 프로젝트 → **"Logs"** 탭

### 재시작
- **"Redeploy"** 버튼으로 서비스 재시작

### 도메인 (선택)
- **"Settings"** → **"Domains"**에서 공개 URL 생성 가능
- 헬스체크용으로 활용 가능

---

## 💰 비용

- **무료 티어**: 월 $5 크레딧 제공
- 소규모 봇은 무료 범위 내에서 24시간 운영 가능
- 초과 시 사용량 기반 과금

---

## ❓ 문제 해결

| 문제 | 해결책 |
|------|--------|
| 빌드 실패 | Dockerfile, requirements.txt 확인 |
| 환경변수 오류 | Variables 탭에서 설정 다시 확인 |
| 봇이 시작 안 됨 | Logs에서 에러 메시지 확인 |
| Telegram 알림 없음 | TELEGRAM_BOT_TOKEN, CHAT_ID 확인 |

---

## 📌 다음 단계

1. Railway 배포 완료
2. Telegram에서 봇 시작 메시지 확인
3. 매매 시그널 발생 시 알림 수신 테스트
