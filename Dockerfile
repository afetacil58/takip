FROM python:3.12-alpine

WORKDIR /app

RUN addgroup -S -g 10001 appuser \
    && adduser -S -D -H -u 10001 -G appuser appuser \
    && mkdir -p /app/uploads /data \
    && chown -R appuser:appuser /app /data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser . .

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp

USER appuser

EXPOSE 5000

CMD ["python", "docker_entrypoint.py"]
