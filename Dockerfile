FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv -i https://mirrors.aliyun.com/pypi/simple/

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

COPY src/ ./src/

COPY front/ ./front/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    PYTHONUNBUFFERED=1
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD [ "python" , "-c" , "import urllib.request;urllib.request.urlopen('http://localhost:8000/health')" ]

CMD [ "uvicorn" , "question_response_agent.main:app" , "--host" , "0.0.0.0" , "--port" , "8000" ]