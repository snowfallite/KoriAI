# Single command hub (tech.md §15.4). Keep one plain command per line:
# recipes run under sh on Linux and macOS and under PowerShell on Windows.
set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

# Windows falls back to the ANSI code page when output is redirected; rich then fails.
export PYTHONUTF8 := "1"

be := "uv --directory backend run"
fe := "pnpm --dir frontend"
py := "uv run --no-project python"

default:
    @just --list

# Install dependencies and the Playwright browser
setup:
    uv --directory backend sync
    {{ fe }} install
    {{ fe }} exec playwright install chromium

# Dev stack on fakes: Postgres, Qdrant and the reloading API in Docker, the SPA on the host
dev:
    docker compose -f docker-compose.dev.yml up -d --build --wait
    {{ fe }} dev

# Format Python and frontend code
fmt:
    {{ be }} ruff format . ../scripts
    {{ fe }} format

# Linters, import boundaries, unused dependencies, forbidden APIs
lint:
    {{ be }} ruff check . ../scripts
    {{ be }} ruff format --check . ../scripts
    {{ be }} lint-imports
    {{ be }} deptry .
    {{ fe }} lint
    {{ py }} scripts/check_forbidden_apis.py

# mypy and svelte-check
typecheck:
    {{ be }} mypy
    {{ fe }} check

# Backend unit, property, contract, agent and golden tests
test:
    {{ be }} pytest -m "not integration"

# Backend integration tests on real Postgres and Qdrant
test-int:
    {{ if path_exists(justfile_directory() / "backend/tests/integration") == "true" { be + " pytest -m integration" } else { "echo 'no integration tests yet'" } }}

# Frontend unit and property tests
test-fe:
    {{ fe }} test

# Playwright end-to-end tests
e2e:
    {{ fe }} test:e2e

# SPA production build
build:
    {{ fe }} build

# e-disclosure discovery for S1-12: hits the real site, run by hand
discover-edisclosure:
    {{ py }} scripts/discover_edisclosure.py

# Zone labels and CORE_VERSION bump against the PR base: just core-guard core-impl
core-guard labels="" base="origin/main":
    {{ py }} scripts/check_contract_bump.py --base={{ base }} --labels={{ labels }}

# Everything the PR gate checks (§20.1): just gate core-impl
gate labels="" base="origin/main": (core-guard labels base) lint typecheck test test-int test-fe build e2e
