FROM python:3.13-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

COPY pyproject.toml ./
RUN pip install --no-cache-dir .
COPY src ./src

EXPOSE 8000
CMD ["sh", "-c", "uvicorn agency_ops.web:app --host 0.0.0.0 --port ${PORT:-8000}"]
