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
# Firefox hangs on start without a writable HOME: the user gets one.
RUN useradd --system --create-home --uid 10001 app && mkdir /data && chown app /data
WORKDIR /app
COPY --from=build /app/.venv .venv
ENV PATH=/app/.venv/bin:$PATH PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
# e-disclosure answers only a windowed browser: Firefox of Playwright with its system libraries,
# and Xvfb as the display of a server (tech.md §8.5). The adapter starts both on first use.
# IPv4 first: the download stalls where the IPv6 route is broken.
RUN apt-get update \
 && apt-get install -y --no-install-recommends xvfb \
 && NODE_OPTIONS=--dns-result-order=ipv4first playwright install --with-deps firefox \
 && rm -rf /var/lib/apt/lists/*
# GIGACHAT_CA_BUNDLE points here (L-07).
COPY infra/certs/russian_trusted_root_ca.pem certs/
COPY backend/app app
# The fakes answer from the seed, F-10 reads reference/issuers.csv (tech.md §15.2).
COPY backend/fixtures fixtures
# The deploy step runs `alembic upgrade head` in this image (tech.md §20.2).
COPY backend/alembic.ini ./
COPY backend/migrations migrations
USER app
EXPOSE 8000
# Only Caddy reaches the API, so its X-Forwarded-For is trusted.
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--no-access-log", "--forwarded-allow-ips", "*"]
