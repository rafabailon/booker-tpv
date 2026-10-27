FROM python:3.13-slim AS builder

WORKDIR /build
COPY requirements.txt ./requirements.txt
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

FROM python:3.13-slim AS test-builder
WORKDIR /build
COPY requirements.txt requirements-dev.txt ./
RUN pip wheel --no-cache-dir --wheel-dir /test-wheels -r requirements-dev.txt

FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY --from=builder /wheels /wheels
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt && rm -rf /wheels

COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY app ./app

RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM runtime AS test
USER root
COPY requirements-dev.txt ./requirements-dev.txt
COPY --from=test-builder /test-wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements-dev.txt && rm -rf /wheels
COPY --chown=appuser:appuser tests ./tests
USER appuser
CMD ["python", "-m", "pytest", "-q"]