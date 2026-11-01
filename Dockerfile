FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.8.11 /uv /usr/local/bin/uv

WORKDIR /srv
COPY backend/pyproject.toml backend/uv.lock backend/
RUN cd backend && uv sync --frozen --no-dev

COPY backend backend
COPY frontend frontend

WORKDIR /srv/backend
ENV PATH="/srv/backend/.venv/bin:$PATH"
# Strict unless told otherwise, so a server missing APP_ENV never runs in development mode.
ENV APP_ENV=production
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
