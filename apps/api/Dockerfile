FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY apps/agent /app/apps/agent
COPY apps/api /app/apps/api

ENV PYTHONUNBUFFERED=1 \
    MES_RELOAD=false \
    MES_SERVER_HOST=0.0.0.0 \
    MES_SERVER_PORT=8765 \
    PYTHONPATH=/app/apps/agent

WORKDIR /app/apps/api
EXPOSE 8765

CMD ["python", "main.py"]
