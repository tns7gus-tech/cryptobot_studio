# CryptoBot Studio 🤖

Upbit 거래소 연동 암호화폐 자동매매 봇

## 📋 주요 기능

- **RSI 기반 매매**: RSI 과매도(30↓) 매수, 과매수(70↑) 매도
- **볼린저밴드 전략**: 하단밴드 매수, 상단밴드 매도
- **결합 전략**: RSI + BB 동시 신호 시 거래
- **텔레그램 알림**: 매수/매도 체결, 신호 감지, 일일 리포트
- **리스크 관리**: 일일 거래 횟수/손실 한도 제한

## 🚀 빠른 시작

### 1. 의존성 설치

```bash
cd D:\projects\cryptobot_studio
pip install -r requirements.txt
```

### 2. 환경 설정

`.env` 파일 수정:

```env
# Telegram (필수)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Upbit API (필수)
UPBIT_ACCESS_KEY=your_access_key
UPBIT_SECRET_KEY=your_secret_key

# 설정
TRADE_SYMBOL=KRW-BTC
TRADE_AMOUNT=10000
BOT_MODE=semi  # semi: 알림만, full: 자동매매
```

### 3. 실행

```bash
cd src
python main.py
```

## 📁 프로젝트 구조

```
cryptobot_studio/
├── src/
│   ├── main.py              # 메인 실행 파일
│   ├── config.py            # 설정 관리
│   ├── upbit_client.py      # Upbit API 클라이언트
│   ├── indicators.py        # 기술 지표 (RSI, BB 등)
│   ├── strategies.py        # 매매 전략
│   ├── trader.py            # 자동매매 엔진
│   ├── telegram_notifier.py # 텔레그램 알림
│   └── risk_manager.py      # 리스크 관리
├── data/                    # 통계 데이터
├── logs/                    # 로그 파일
├── .env                     # 환경 변수
└── requirements.txt         # Python 의존성
```

## ⚙️ 설정 옵션

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `TRADE_SYMBOL` | 거래 마켓 | KRW-BTC |
| `TRADE_AMOUNT` | 1회 거래 금액 (KRW) | 10,000 |
| `RSI_PERIOD` | RSI 계산 기간 | 14 |
| `RSI_BUY_THRESHOLD` | RSI 매수 기준 | 30 |
| `RSI_SELL_THRESHOLD` | RSI 매도 기준 | 70 |
| `BB_PERIOD` | 볼린저밴드 기간 | 20 |
| `MAX_DAILY_TRADES` | 일일 최대 거래 | 10 |
| `MAX_DAILY_LOSS` | 일일 손실 한도 (KRW) | 50,000 |

## 🔔 봇 모드

### Semi-auto (semi)
- 신호 발생 시 **텔레그램 알림만** 발송
- 실제 거래는 사용자가 직접 수행
- 안전한 테스트/모니터링용

### Full-auto (full)
- 신호 발생 시 **자동 매매** 실행
- 리스크 관리 규칙 자동 적용
- ⚠️ 실제 자금 거래 주의

## 📊 알림 예시

### 매수 신호 (Semi-auto)
```
🟢 매수 신호 감지
━━━━━━━━━━━━━━━━━━━━━
📊 BTC/KRW
💰 현재가: ₩145,230,000
🎯 신뢰도: 75%
📝 사유: RSI 28.5 < 30 (과매도)
━━━━━━━━━━━━━━━━━━━━━
```

### 매수 체결 (Full-auto)
```
🟢 매수 체결
━━━━━━━━━━━━━━━━━━━━━
📊 BTC/KRW
💰 매수가: ₩145,230,000
📦 수량: 0.00006883 BTC
💵 금액: ₩10,000
📉 RSI: 28.5 (과매도)
🎯 전략: RSI+BB
━━━━━━━━━━━━━━━━━━━━━
```

## ⚠️ 주의사항

- **백테스트 결과는 과거 성과이며 미래 수익을 보장하지 않습니다**
- API 키는 절대 공개하지 마세요
- 소액으로 먼저 테스트하세요
- `semi` 모드로 충분히 테스트 후 `full` 모드 사용

## 📝 라이선스

MIT License

---

**작성일:** 2026-01-13
**버전:** 0.1.0
