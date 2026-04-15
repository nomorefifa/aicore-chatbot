FROM python:3.11-slim

WORKDIR /app

# 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 코드 복사
COPY . .

# 시작 스크립트
RUN chmod +x start.sh

CMD ["./start.sh"]
