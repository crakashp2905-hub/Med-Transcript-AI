FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY apps/clinician-web/package*.json ./
RUN npm ci
COPY apps/clinician-web/ ./
RUN npm run build

FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml README.md constraints-ci.txt ./
COPY services/ ./services/
RUN python -m pip install --no-cache-dir --upgrade pip==26.2.2 && python -m pip install --no-cache-dir -c constraints-ci.txt '.[asr,postgres]'
COPY --from=web /web/dist ./apps/clinician-web/dist
RUN useradd --create-home --uid 10001 medscribe && mkdir -p /app/data/assets && chown -R medscribe:medscribe /app/data
USER medscribe
EXPOSE 8000
CMD ["python", "-m", "services.launch", "--no-worker", "--host", "0.0.0.0"]
