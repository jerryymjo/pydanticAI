FROM python:3.12-slim
WORKDIR /app

# lxml 빌드 의존성 (trafilatura)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential libxml2-dev libxslt1-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Chromium + 시스템 의존성 설치 (Playwright)
RUN playwright install --with-deps chromium

COPY src/ ./
COPY scripts/ scripts/
CMD ["python", "bot.py"]
