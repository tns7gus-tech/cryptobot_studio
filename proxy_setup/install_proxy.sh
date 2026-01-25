#!/bin/bash

# ==========================================
# CryptoBot Proxy Setup Script for Ubuntu
# ==========================================
# 이 스크립트는 Ubuntu VPS를 나만의 프록시 서버로 만들어줍니다.
# 실행 방법: bash install_proxy.sh <사용자아이디> <비밀번호>
# 예시: bash install_proxy.sh mybot securepass123

USER=$1
PASS=$2
PORT=3128

if [ -z "$USER" ] || [ -z "$PASS" ]; then
    echo "❌ 사용법 오류: 사용자 아이디와 비밀번호를 입력해주세요."
    echo "사용법: bash install_proxy.sh <사용자아이디> <비밀번호>"
    exit 1
fi

echo "🚀 프록시 서버 설치를 시작합니다..."

# 1. 패키지 업데이트 및 Squid 설치
apt-get update
apt-get install -y squid apache2-utils

# 2. 비밀번호 파일 생성
htpasswd -bc /etc/squid/passwd "$USER" "$PASS"

# 3. Squid 설정 파일 백업
cp /etc/squid/squid.conf /etc/squid/squid.conf.backup

# 4. Squid 설정 작성
cat <<EOF > /etc/squid/squid.conf
auth_param basic program /usr/lib/squid/basic_ncsa_auth /etc/squid/passwd
auth_param basic children 5
auth_param basic realm CryptoBot Proxy
auth_param basic credentialsttl 2 hours
acl auth_users proxy_auth REQUIRED

acl SSL_ports port 443
acl Safe_ports port 80          # http
acl Safe_ports port 21          # ftp
acl Safe_ports port 443         # https
acl Safe_ports port 70          # gopher
acl Safe_ports port 210         # wais
acl Safe_ports port 1025-65535  # unregistered ports
acl Safe_ports port 280         # http-mgmt
acl Safe_ports port 488         # gss-http
acl Safe_ports port 591         # filemaker
acl Safe_ports port 777         # multiling http
acl CONNECT method CONNECT

# 내 봇 사용자만 허용
http_access allow auth_users
http_access deny all

http_port $PORT
coredump_dir /var/spool/squid

# 익명성 강화 (IP 숨김)
forwarded_for off
request_header_access Via deny all
request_header_access X-Forwarded-For deny all
EOF

# 5. 서비스 재시작
systemctl restart squid
systemctl enable squid

# 6. 방화벽 설정 (UFW가 켜져있는 경우)
if ufw status | grep -q "Active"; then
    ufw allow $PORT/tcp
    echo "🔓 방화벽 포트 $PORT 개방 완료"
fi

# 7. 결과 출력
IP=$(curl -s ifconfig.me)

echo ""
echo "✅ 설치가 완료되었습니다!"
echo "---------------------------------------------------"
echo "🌐 Railway PROXY_URL 설정값:"
echo "http://$USER:$PASS@$IP:$PORT"
echo "---------------------------------------------------"
echo "이 주소를 복사해서 Railway 변수에 넣으세요."
