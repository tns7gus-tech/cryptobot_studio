# 🐋 Polymarket Whale Bot - Google Cloud Run 배포 가이드

## 📋 개요

**Polymarket Whale Bot**은 $10,000 이상의 대규모 거래를 실시간 감지하고, Google Gemini AI로 내부자 거래 가능성을 분석하여 자동으로 베팅하는 24/7 봇입니다.

### 주요 기능
- 🐋 **고래 거래 감지**: $10,000 이상 거래 실시간 모니터링
- 🤖 **AI 분석**: Gemini Pro로 내부자 거래 패턴 분석
- 📊 **리스크 관리**: 일일 베팅 횟수/금액/손실 한도
- 📱 **Telegram 알림**: 실시간 알림 및 일일 리포트
- 🎯 **자동 베팅**: 반자동/완전자동 모드 선택

---

## 🚀 빠른 시작

### 1단계: 사전 준비

#### Google Cloud 계정
1. [Google Cloud Console](https://console.cloud.google.com) 접속
2. 새 프로젝트 생성
3. 프로젝트 ID 기록 (예: `my-polymarket-bot`)

#### gcloud CLI 설치
```powershell
# Windows
# https://cloud.google.com/sdk/docs/install 에서 다운로드

# 설치 후 로그인
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

#### Telegram Bot 생성
1. [@BotFather](https://t.me/botfather)에서 `/newbot` 실행
2. Bot Token 복사
3. [@userinfobot](https://t.me/userinfobot)에서 Chat ID 확인

#### Google AI API Key
- 이미 Google One AI Premium 구독 중이므로 API 키 사용 가능
- [Google AI Studio](https://makersuite.google.com/app/apikey)에서 발급

---

### 2단계: 환경 설정

`.env` 파일 생성:

```env
# Telegram
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id

# Google AI
GOOGLE_AI_API_KEY=your_google_ai_api_key

# Bot Mode (semi or full)
BOT_MODE=semi

# Whale Detection
WHALE_THRESHOLD=10000
MAX_BET_AMOUNT=50
MAX_DAILY_BETS=5
MAX_DAILY_LOSS=200

# Polymarket (FULL AUTO MODE만 필요)
# POLYMARKET_PRIVATE_KEY=your_private_key
# POLYMARKET_FUNDER_ADDRESS=your_funder_address
```

---

### 3단계: Cloud Run 배포

```powershell
# 프로젝트 디렉토리로 이동
cd d:\projects\polymarket_monitor

# 배포 스크립트 실행
.\deploy_cloudrun.ps1 -ProjectId "your-project-id" -Mode "semi"
```

**배포 과정**:
1. ✅ GCP 프로젝트 설정
2. ✅ 필요한 API 활성화
3. ✅ Secret Manager에 비밀 저장
4. ✅ Docker 이미지 빌드
5. ✅ Cloud Run에 배포

**예상 시간**: 5-10분

---

## 📊 모니터링

### 로그 확인
```powershell
# 실시간 로그
gcloud run services logs tail polymarket-whale-bot --region=us-central1

# 최근 로그
gcloud run services logs read polymarket-whale-bot --region=us-central1 --limit=50
```

### 서비스 상태
```powershell
gcloud run services describe polymarket-whale-bot --region=us-central1
```

### Cloud Console
[Cloud Run Console](https://console.cloud.google.com/run)에서:
- 📊 CPU/메모리 사용량
- 📈 요청 수
- 🔍 로그 검색
- ⚙️ 설정 변경

---

## 💰 비용

### 예상 월 비용
| 항목 | 비용 |
|------|------|
| Cloud Run (1 인스턴스, CPU always-on) | ~$14 |
| Secret Manager | $0 (무료 티어) |
| Cloud Storage (로그) | ~$0.50 |
| **총계** | **~$14.50/월** |

### 비용 최적화
- 무료 티어: 월 180,000 vCPU-초 (약 $4 할인)
- 실제 비용: **~$10-14/월**

---

## 🎯 운영 모드

### Semi-Auto Mode (반자동) - 권장
```env
BOT_MODE=semi
```

**동작**:
- ✅ 고래 거래 감지
- ✅ AI 분석
- ✅ Telegram 알림
- ❌ 자동 베팅 안 함

**장점**:
- 안전 (수동 확인 후 베팅)
- 법적 리스크 낮음
- 전략 검증 가능

**추천 대상**: 초기 테스트, 전략 학습

---

### Full-Auto Mode (완전자동) - 고급
```env
BOT_MODE=full
POLYMARKET_PRIVATE_KEY=your_key
POLYMARKET_FUNDER_ADDRESS=your_address
```

**동작**:
- ✅ 고래 거래 감지
- ✅ AI 분석
- ✅ **자동 베팅** (AI 신뢰도 70% 이상)
- ✅ Telegram 알림

**주의사항**:
- ⚠️ 자금 손실 위험
- ⚠️ False Positive 가능
- ⚠️ 법적 리스크

**추천 대상**: 전략 검증 완료 후

---

## 📱 Telegram 알림 예시

### 고래 거래 감지
```
🔴 WHALE DETECTED 🔴

💰 Amount: $50,000
📊 Side: BUY
💵 Price: 0.05

📍 Market: Will there be US military action in 2024?

👤 Wallet Analysis:
• Address: 0x1234567890ab...
• Age: 3 days
• New wallet: ✅ YES

📈 Market Analysis:
• Rank: #75
• Niche market: ✅ YES

🤖 AI Analysis:
• Insider probability: 85%
• Recommendation: 🎯 BET
• Reasoning: 신규 지갑이 틈새 마켓에 대량 베팅...

⚠️ Suspicion Level: HIGH (0.85)
```

### 자동 베팅 완료 (Full Auto)
```
✅ TRADE SUCCESS ✅

🎯 Order Details:
• Order ID: abc123def456
• Amount: $50.00
• Side: BUY
• Price: 0.05

📊 Market: Will there be US military action...

🤖 AI Confidence: 85%
```

### 일일 리포트
```
📊 DAILY REPORT 📊

💰 Performance:
• Total bets: 3
• Total wagered: $150.00
• Net profit: 📈 $+25.50
• Win rate: 66.7%
• Wins: 2 | Losses: 1

🤖 AI Analysis:
오늘은 3건의 거래를 실행했으며...
```

---

## ⚙️ 설정 변경

### 임계값 조정
```env
# 고래 기준 금액
WHALE_THRESHOLD=20000  # $20,000로 상향

# 최대 베팅 금액
MAX_BET_AMOUNT=100  # $100로 상향

# 일일 베팅 횟수
MAX_DAILY_BETS=10  # 10회로 상향
```

### 재배포
```powershell
# 설정 변경 후 재배포
.\deploy_cloudrun.ps1 -ProjectId "your-project-id" -Mode "semi"
```

---

## 🔧 문제 해결

### "Secret not found"
```powershell
# Secret 수동 생성
echo "your_token" | gcloud secrets create telegram-bot-token --data-file=-
```

### "Deployment failed"
```powershell
# 로그 확인
gcloud builds log --region=us-central1

# 권한 확인
gcloud projects get-iam-policy YOUR_PROJECT_ID
```

### "Bot not responding"
```powershell
# 서비스 재시작
gcloud run services update polymarket-whale-bot --region=us-central1
```

---

## 📈 성과 추적

### CSV 로그
- 위치: Cloud Storage 버킷
- 파일: `trades/YYYY-MM-DD.csv`
- 내용: 모든 거래 내역

### 분석
```python
import pandas as pd

# CSV 다운로드
df = pd.read_csv('trades/2024-01-11.csv')

# 승률 계산
win_rate = df['profit'].gt(0).mean()
print(f"Win rate: {win_rate:.2%}")

# 총 수익
total_profit = df['profit'].sum()
print(f"Total profit: ${total_profit:.2f}")
```

---

## 🛑 중지 및 삭제

### 일시 중지
```powershell
# 최소 인스턴스 0으로 설정 (비용 절감)
gcloud run services update polymarket-whale-bot \
    --min-instances=0 \
    --region=us-central1
```

### 완전 삭제
```powershell
# 서비스 삭제
gcloud run services delete polymarket-whale-bot --region=us-central1

# Secret 삭제
gcloud secrets delete telegram-bot-token
gcloud secrets delete telegram-chat-id
gcloud secrets delete google-ai-key
```

---

## ⚠️ 법적 고지

1. **자금 손실 위험**: 모든 베팅은 본인 책임
2. **ToS 위반 가능성**: Polymarket 약관 확인 필요
3. **규제 리스크**: 거주 지역 법률 확인
4. **세금**: 수익 발생 시 세금 신고 의무

---

## 📞 지원

### 로그 확인
```powershell
# 에러 로그만
gcloud run services logs read polymarket-whale-bot \
    --region=us-central1 \
    --filter="severity=ERROR"
```

### 디버깅
```powershell
# 로컬 테스트
python main_bot.py
```

---

## 🎯 다음 단계

1. ✅ **1주차**: Semi-auto 모드로 데이터 수집
2. 📊 **2주차**: 패턴 분석 및 전략 검증
3. 🎯 **3주차**: Full-auto 모드 전환 고려
4. 📈 **4주차+**: 수익 극대화

---

**행운을 빕니다! 🚀**
