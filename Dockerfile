## PROD STEP
FROM ghcr.io/astral-sh/uv:python3.14-alpine

ENV PATH="/app/.venv/bin:$PATH"
ENV TZ=Europe/Paris

WORKDIR /app

COPY pyproject.toml uv.lock mamietv.toml app.py precompress.py ./
COPY templates ./templates/
COPY utils ./utils/
COPY static ./static/

RUN uv sync --frozen --no-cache --no-dev --no-editable --compile-bytecode \
	&& addgroup -S mamietv \
	&& adduser -S -G mamietv mamietv \
	&& chown -R mamietv:mamietv /app

# The scheduler renders pages into /app/static at runtime, so that tree must
# stay writable by the unprivileged user; everything else is read-only.
USER mamietv

EXPOSE 8000

# /healthz is a tiny route, not a full page render. busybox wget ships with the
# base image, so curl is not needed.
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
	CMD wget -q -O /dev/null http://127.0.0.1:8000/healthz || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
