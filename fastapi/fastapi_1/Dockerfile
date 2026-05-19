FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .

# 테스트 목적이므로 패키지 설치는 최소화 (fastapi와 uvicorn만 설치)
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]