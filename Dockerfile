FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs \
    npm \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN npm install -g @maximhq/bifrost

COPY . .

ENV PORT=8005
EXPOSE 8005

CMD ["sh", "-c", "python scripts/run_bifrost.py & sleep 4 && python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8005}"]
