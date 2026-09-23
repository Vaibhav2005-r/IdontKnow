# Slim, non-root, model baked in at build time -- the image IS the deployable
# artifact for one model version. docker-compose overrides CMD for the
# dashboard service so this single image serves both the Flask app and
# Streamlit dashboard.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FEEDBACK_DB_PATH=/app/data/feedback/feedback.db \
    MODEL_REGISTRY_PATH=/app/models/registry.json

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ml/ ml/
COPY app/ app/
COPY dashboard/ dashboard/
COPY wsgi.py .
COPY models/ models/

RUN mkdir -p data/feedback artifacts \
    && useradd --create-home --shell /bin/bash phishguard \
    && chown -R phishguard:phishguard /app

USER phishguard

EXPOSE 5000 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health', timeout=3)" || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "wsgi:app"]
