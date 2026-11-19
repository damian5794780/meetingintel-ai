FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATABASE_PATH=/app/data/meetingintel.db
COPY apps/api/requirements-lock.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home appuser && mkdir /app/data && chown appuser /app/data
COPY apps/__init__.py ./apps/
COPY apps/api/*.py ./apps/api/
COPY apps/api/agents/ ./apps/api/agents/
COPY apps/api/routes/ ./apps/api/routes/
COPY apps/api/schemas/ ./apps/api/schemas/
COPY apps/api/services/ ./apps/api/services/
USER appuser
EXPOSE 8000
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
