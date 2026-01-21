FROM python:3.9-slim

WORKDIR /app

# logs 디렉토리 생성
RUN mkdir -p logs

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사
COPY src/ ./src/

# 환경변수
ENV PYTHONUNBUFFERED=1

# 실행
CMD ["python", "src/main.py"]
