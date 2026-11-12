FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN useradd --create-home --shell /usr/sbin/nologin appuser

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY data ./data

RUN pip install --no-cache-dir ".[api]" \
    && mkdir -p /app/reports \
    && chown -R appuser:appuser /app

USER appuser

# `docval eval` scores the local parser and the deterministic extractor.
ENTRYPOINT ["docval"]
CMD ["eval", "--golden", "data/golden", "--out", "reports/eval"]
