FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --no-install-project --frozen 2>/dev/null || uv sync --no-dev --no-install-project

COPY kazo/ kazo/
RUN uv sync --no-dev --frozen 2>/dev/null || uv sync --no-dev \
    && uv run python -c "import kaleido; kaleido.get_chrome_sync()"

CMD ["uv", "run", "python", "-m", "kazo"]
