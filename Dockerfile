FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./

# 安裝必要工具（含 mysqldump）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libssl-dev libffi-dev python3-dev libpq-dev gcc \
    default-mysql-client \
 && pip install --no-cache-dir -r requirements.txt \
 && apt-get purge -y build-essential gcc python3-dev libffi-dev libssl-dev libpq-dev \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

COPY main.py ./
COPY web ./web
COPY backup ./backup
RUN mkdir -p /app/uploads /backup

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
