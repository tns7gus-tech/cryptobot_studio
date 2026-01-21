# Cloud Run 고정 IP 배포 가이드

CryptoBot Studio를 Google Cloud Run에 배포하고 Upbit API용 고정 IP를 설정하는 방법입니다.

## 📋 사전 요구사항

- Google Cloud 계정 및 프로젝트
- gcloud CLI 설치 완료
- Docker Desktop 설치

---

## 🔧 Step 1: VPC 네트워크 설정

### 1.1 VPC 서브넷 생성

```bash
# 프로젝트 ID 설정
export PROJECT_ID="your-project-id"
export REGION="asia-northeast3"  # 서울 리전

gcloud config set project $PROJECT_ID

# VPC 네트워크 생성 (없으면)
gcloud compute networks create cryptobot-vpc --subnet-mode=custom

# 서브넷 생성
gcloud compute networks subnets create cryptobot-subnet \
    --network=cryptobot-vpc \
    --region=$REGION \
    --range=10.8.0.0/28
```

### 1.2 Serverless VPC Access 커넥터 생성

```bash
# VPC Access API 활성화
gcloud services enable vpcaccess.googleapis.com

# VPC 커넥터 생성
gcloud compute networks vpc-access connectors create cryptobot-connector \
    --region=$REGION \
    --network=cryptobot-vpc \
    --range=10.9.0.0/28 \
    --min-instances=2 \
    --max-instances=3
```

---

## 🌐 Step 2: Cloud NAT 설정 (고정 IP)

### 2.1 고정 외부 IP 예약

```bash
# 고정 IP 예약
gcloud compute addresses create cryptobot-nat-ip \
    --region=$REGION

# 예약된 IP 확인 (이 IP를 Upbit에 등록!)
gcloud compute addresses describe cryptobot-nat-ip \
    --region=$REGION \
    --format="value(address)"
```

### 2.2 Cloud Router 생성

```bash
gcloud compute routers create cryptobot-router \
    --network=cryptobot-vpc \
    --region=$REGION
```

### 2.3 Cloud NAT 생성

```bash
gcloud compute routers nats create cryptobot-nat \
    --router=cryptobot-router \
    --region=$REGION \
    --nat-custom-subnet-ip-ranges=cryptobot-subnet \
    --nat-external-ip-pool=cryptobot-nat-ip
```

---

## 🐳 Step 3: Docker 이미지 빌드

### 3.1 Dockerfile 생성

프로젝트 루트에 `Dockerfile` 생성:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사
COPY src/ ./src/
COPY .env .

# 환경변수
ENV PYTHONUNBUFFERED=1

# 실행
CMD ["python", "src/main.py"]
```

### 3.2 이미지 빌드 및 푸시

```bash
# Artifact Registry API 활성화
gcloud services enable artifactregistry.googleapis.com

# 리포지토리 생성
gcloud artifacts repositories create cryptobot-repo \
    --repository-format=docker \
    --location=$REGION

# Docker 인증
gcloud auth configure-docker ${REGION}-docker.pkg.dev

# 이미지 빌드 및 푸시
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/cryptobot-repo/cryptobot:latest .
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/cryptobot-repo/cryptobot:latest
```

---

## 🚀 Step 4: Cloud Run 배포

```bash
# Cloud Run API 활성화
gcloud services enable run.googleapis.com

# Cloud Run 서비스 배포 (VPC 커넥터 연결)
gcloud run deploy cryptobot-studio \
    --image=${REGION}-docker.pkg.dev/${PROJECT_ID}/cryptobot-repo/cryptobot:latest \
    --region=$REGION \
    --vpc-connector=cryptobot-connector \
    --vpc-egress=all-traffic \
    --no-allow-unauthenticated \
    --memory=512Mi \
    --timeout=3600 \
    --min-instances=1 \
    --max-instances=1
```

> **중요**: `--vpc-egress=all-traffic` 옵션이 모든 아웃바운드 트래픽을 VPC를 통해 라우팅합니다.

---

## 🔑 Step 5: Upbit API IP 등록

1. [Upbit Open API 관리](https://upbit.com/mypage/open_api_management) 접속
2. API 키 생성 또는 수정
3. **허용 IP 주소**에 Step 2.1에서 확인한 고정 IP 입력
4. 필요 권한 선택: ✅ 자산조회, ✅ 주문조회, ✅ 주문하기

---

## 📊 Step 6: 환경변수 설정 (Secret Manager 권장)

### 6.1 Secret Manager 사용 (보안)

```bash
# Secret Manager API 활성화
gcloud services enable secretmanager.googleapis.com

# 시크릿 생성
echo -n "your_upbit_access_key" | gcloud secrets create upbit-access-key --data-file=-
echo -n "your_upbit_secret_key" | gcloud secrets create upbit-secret-key --data-file=-
echo -n "your_telegram_bot_token" | gcloud secrets create telegram-bot-token --data-file=-
echo -n "your_telegram_chat_id" | gcloud secrets create telegram-chat-id --data-file=-

# Cloud Run에 시크릿 연결
gcloud run services update cryptobot-studio \
    --region=$REGION \
    --set-secrets=UPBIT_ACCESS_KEY=upbit-access-key:latest,UPBIT_SECRET_KEY=upbit-secret-key:latest,TELEGRAM_BOT_TOKEN=telegram-bot-token:latest,TELEGRAM_CHAT_ID=telegram-chat-id:latest
```

---

## ✅ 배포 확인

```bash
# 로그 확인
gcloud run services logs read cryptobot-studio --region=$REGION --limit=50

# 서비스 상태 확인
gcloud run services describe cryptobot-studio --region=$REGION
```

---

## 💰 예상 비용 (월간)

| 서비스 | 비용 |
|--------|------|
| Cloud Run (min-instances=1) | ~$5-10 |
| VPC Connector | ~$0.01/시간 = ~$7 |
| Cloud NAT | ~$0.045/시간 = ~$32 |
| 고정 IP | 무료 (사용 중일 때) |
| **합계** | **~$45-50/월** |

> 💡 **비용 절감 팁**: Cloud NAT 대신 Compute Engine VM (e2-micro 무료 티어)을 사용하면 월 $5 이하로 가능합니다.

---

## 🛠️ 빠른 명령어 요약

```bash
# 1. 고정 IP 확인
gcloud compute addresses describe cryptobot-nat-ip --region=asia-northeast3 --format="value(address)"

# 2. 재배포
gcloud run deploy cryptobot-studio --image=${REGION}-docker.pkg.dev/${PROJECT_ID}/cryptobot-repo/cryptobot:latest --region=asia-northeast3

# 3. 로그 확인
gcloud run services logs tail cryptobot-studio --region=asia-northeast3
```
