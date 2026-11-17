# Pickup backend: API, telephony webhooks and the real-time voice agent in one service.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
RUN pip install --upgrade pip && pip install .

RUN useradd --create-home pickup && mkdir -p /app/recordings && chown -R pickup /app
USER pickup

EXPOSE 8000
# Run migrations, then serve. One worker per container: each live call holds a WebSocket and
# a voice pipeline in memory, so scale out with more containers behind the load balancer.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
