# Pickup backend: API, telephony webhooks and the real-time voice agent in one service.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
RUN pip install --upgrade pip && pip install .

COPY docker-entrypoint.sh ./
RUN useradd --create-home pickup && mkdir -p /app/recordings && chown -R pickup /app

EXPOSE 8000
# The entrypoint drops to the "pickup" user, runs migrations, then serves. One worker per
# container: each live call holds a WebSocket and a voice pipeline in memory, so scale out with
# more containers behind the load balancer.
ENTRYPOINT ["/app/docker-entrypoint.sh"]
