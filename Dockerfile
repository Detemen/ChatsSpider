FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-spider.txt .
RUN pip install --no-cache-dir -r requirements-spider.txt

COPY spider_telethon.py database.py channelsdb.txt ./

RUN mkdir -p accs output

CMD ["python3", "-u", "spider_telethon.py"]
