# Compute Engine VM 배포 가이드 (저비용)

CryptoBot Studio를 Google Compute Engine에 배포하는 방법입니다.

**예상 비용: $0 ~ $5/월** (Free Tier 활용 시)

---

## 🚀 Step 1: VM 인스턴스 생성

```bash
# 프로젝트 설정
export PROJECT_ID="your-project-id"
gcloud config set project $PROJECT_ID

# e2-micro VM 생성 (Free Tier!)
gcloud compute instances create cryptobot-vm \
    --zone=us-central1-a \
    --machine-type=e2-micro \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=10GB \
    --tags=cryptobot
```

> 💡 **Free Tier 조건**: `us-central1`, `us-east1`, `us-west1` 리전에서 e2-micro 1대 무료

---

## 🌐 Step 2: 고정 IP 설정

```bash
# 고정 IP 예약
gcloud compute addresses create cryptobot-ip \
    --region=us-central1

# IP 확인 (이 IP를 Upbit에 등록!)
gcloud compute addresses describe cryptobot-ip \
    --region=us-central1 \
    --format="value(address)"

# VM에 고정 IP 연결
gcloud compute instances delete-access-config cryptobot-vm \
    --zone=us-central1-a \
    --access-config-name="external-nat"

gcloud compute instances add-access-config cryptobot-vm \
    --zone=us-central1-a \
    --address=$(gcloud compute addresses describe cryptobot-ip --region=us-central1 --format="value(address)")
```

---

## 📦 Step 3: VM에 코드 배포

### 3.1 SSH 접속

```bash
gcloud compute ssh cryptobot-vm --zone=us-central1-a
```

### 3.2 환경 설정 (VM 내부에서 실행)

```bash
# Python 설치
sudo apt update
sudo apt install -y python3-pip python3-venv git

# 프로젝트 폴더 생성
mkdir -p ~/cryptobot && cd ~/cryptobot

# 가상환경 생성
python3 -m venv venv
source venv/bin/activate
```

### 3.3 코드 업로드 (로컬에서)

```bash
# 로컬에서 VM으로 파일 복사
gcloud compute scp --recurse D:\projects\cryptobot_studio\* cryptobot-vm:~/cryptobot/ --zone=us-central1-a
```

### 3.4 의존성 설치 (VM 내부)

```bash
cd ~/cryptobot
source venv/bin/activate
pip install -r requirements.txt
```

---

## 🔑 Step 4: 환경변수 설정

VM에서 `.env` 파일 수정:

```bash
nano ~/cryptobot/.env
```

```env
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
UPBIT_ACCESS_KEY=your_access_key  
UPBIT_SECRET_KEY=your_secret_key
TRADE_SYMBOL=KRW-BTC
TRADE_AMOUNT=10000
BOT_MODE=semi
```

---

## ⚙️ Step 5: systemd 서비스 등록 (24시간 실행)

```bash
# 서비스 파일 생성
sudo nano /etc/systemd/system/cryptobot.service
```

내용:

```ini
[Unit]
Description=CryptoBot Studio
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/cryptobot
Environment=PATH=/home/YOUR_USERNAME/cryptobot/venv/bin
ExecStart=/home/YOUR_USERNAME/cryptobot/venv/bin/python src/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

> ⚠️ `YOUR_USERNAME`을 실제 사용자명으로 변경하세요 (`whoami` 명령으로 확인)

```bash
# 서비스 활성화 및 시작
sudo systemctl daemon-reload
sudo systemctl enable cryptobot
sudo systemctl start cryptobot

# 상태 확인
sudo systemctl status cryptobot

# 로그 확인
sudo journalctl -u cryptobot -f
```

---

## 🔑 Step 6: Upbit API IP 등록

1. [Upbit Open API 관리](https://upbit.com/mypage/open_api_management)
2. Step 2에서 확인한 **고정 IP** 등록
3. 권한: ✅ 자산조회, ✅ 주문조회, ✅ 주문하기

---

## 💰 비용 비교

| 항목 | Cloud Run + NAT | Compute Engine |
|------|-----------------|----------------|
| 서버 | ~$10 | **$0** (e2-micro) |
| VPC/NAT | ~$40 | $0 |
| 고정 IP | $0 | $0 |
| **합계** | **~$50/월** | **~$0/월** |

---

## 🛠️ 유용한 명령어

```bash
# SSH 접속
gcloud compute ssh cryptobot-vm --zone=us-central1-a

# 서비스 재시작
sudo systemctl restart cryptobot

# 실시간 로그
sudo journalctl -u cryptobot -f

# 서비스 중지
sudo systemctl stop cryptobot
```

---

## ⚠️ 주의사항

- **리전**: us-central1 권장 (Free Tier)
- **레이턴시**: 한국 Upbit API 호출 시 ~200ms 지연 (트레이딩에 큰 영향 없음)
- **보안**: `.env` 파일 권한 설정 `chmod 600 .env`
