FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HF_HOME=/app/model-cache OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false
WORKDIR /app
RUN pip install --no-cache-dir uv==0.12.10
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-cache
COPY scripts ./scripts
COPY data/knowledge/raw_verified ./data/knowledge/raw_verified
RUN useradd --create-home --uid 10001 guanchen && mkdir -p /app/model-cache && chown -R guanchen:guanchen /app
USER guanchen
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=6s --start-period=300s CMD ["/app/.venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/ready', timeout=5)"]
CMD ["/app/.venv/bin/python", "-m", "uvicorn", "guanchen_v2.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
