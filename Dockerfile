FROM python:3.13-alpine

WORKDIR /app
COPY server /app/server

ENV PYTHONUNBUFFERED=1 \
    SMS_GATEWAY_HOST=0.0.0.0 \
    SMS_GATEWAY_PORT=8787 \
    SMS_GATEWAY_DB=/data/gateway.db

VOLUME ["/data"]
EXPOSE 8787

CMD ["python", "-m", "server.app"]

