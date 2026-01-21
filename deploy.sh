#!/bin/bash
# CryptoBot Studio - 원클릭 배포 스크립트

PROJECT_ID="${1:-$(gcloud config get-value project)}"
ZONE="us-central1-a"
REGION="us-central1"
VM_NAME="cryptobot-vm"

echo "🚀 CryptoBot Studio 배포 시작..."
echo "📦 프로젝트: $PROJECT_ID"

# 1. VM 생성
echo "1️⃣ VM 생성 중..."
gcloud compute instances create $VM_NAME \
    --project=$PROJECT_ID \
    --zone=$ZONE \
    --machine-type=e2-micro \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=10GB 2>/dev/null || echo "VM already exists"

# 2. 고정 IP 예약 및 연결
echo "2️⃣ 고정 IP 설정 중..."
gcloud compute addresses create cryptobot-ip --region=$REGION 2>/dev/null || true
STATIC_IP=$(gcloud compute addresses describe cryptobot-ip --region=$REGION --format="value(address)")

gcloud compute instances delete-access-config $VM_NAME --zone=$ZONE --access-config-name="external-nat" 2>/dev/null || true
gcloud compute instances add-access-config $VM_NAME --zone=$ZONE --address=$STATIC_IP 2>/dev/null || true

echo ""
echo "✅ 배포 완료!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 고정 IP: $STATIC_IP"
echo "👆 이 IP를 Upbit API에 등록하세요!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📌 다음 명령어로 SSH 접속:"
echo "   gcloud compute ssh $VM_NAME --zone=$ZONE"
