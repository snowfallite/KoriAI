# Caddy with the built SPA (tech.md §20.2). Build context: the repo root.
FROM node:24.21.0-trixie-slim AS spa
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable
WORKDIR /src
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml frontend/.npmrc ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
# The kitchen-sink ships only in a build with PUBLIC_KITCHEN_SINK=1: the CI stack (§15.3).
ARG PUBLIC_KITCHEN_SINK=0
RUN pnpm build

FROM caddy:2.11.4-alpine
COPY infra/caddy/Caddyfile /etc/caddy/Caddyfile
COPY --from=spa /src/build /srv
