FROM python:3.12-slim AS build

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev

FROM python:3.12-slim
RUN useradd -r -u 10001 app
COPY --from=build /app /app
USER app
ENV PATH="/app/.venv/bin:$PATH"
CMD ["uvicorn", "dockship.main:app", "--host", "0.0.0.0", "--port", "8000"]
