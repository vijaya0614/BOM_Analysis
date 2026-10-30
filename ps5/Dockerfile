FROM node:22-alpine AS frontend-build
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=demo
WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && mkdir -p /app/data
COPY . ./
COPY --from=frontend-build /app/web/dist ./web/dist
EXPOSE 10000
CMD ["sh", "-c", "python -m alembic upgrade head && exec python -m uvicorn src.api.main:app --host 0.0.0.0 --port 10000"]
