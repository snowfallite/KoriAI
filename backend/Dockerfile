# API image (tech.md §20.2). Build context: the repo root, for infra/certs.
FROM python:3.13.15-slim-trixie AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# The T-Bank index sends no intermediate certificate (L-04).
COPY infra/certs/russian_trusted_root_ca.pem /tmp/russian_ca.pem
RUN cat /etc/ssl/certs/ca-certificates.crt /tmp/russian_ca.pem > /tmp/ca.pem
COPY backend/pyproject.toml backend/uv.lock ./
RUN SSL_CERT_FILE=/tmp/ca.pem uv sync --frozen --no-dev

FROM python:3.13.15-slim-trixie
RUN useradd --system --uid 10001 app && mkdir /data && chown app /data
WORKDIR /app
COPY --from=build /app/.venv .venv
# GIGACHAT_CA_BUNDLE points here (L-07).
COPY infra/certs/russian_trusted_root_ca.pem certs/
COPY backend/app app
ENV PATH=/app/.venv/bin:$PATH
USER app
EXPOSE 8000
# Only Caddy reaches the API, so its X-Forwarded-For is trusted.
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--no-access-log", "--forwarded-allow-ips", "*"]
