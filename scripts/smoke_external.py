"""Smoke of the external APIs with real keys (tech.md §15.4; S1-09 AC 4). Never runs in CI.

`just smoke-external [--skip-context]` from the repo root. Keys come from the environment, .env
and backend/.env, as the API reads them. The checks go through the real adapters; model calls go
through metering, so llm_calls and usage_daily count them while the database answers.

Writes docs/sources/smoke-<date>.md. Costs: a call with a function per model family, two calls
for the prompt cache, probes of 32k and 128k tokens per family for the context windows (skip them
with --skip-context), one Tavily credit, a few T-Invest reads, nine logos of the T-Invest CDN,
robots.txt and one card of e-disclosure.
"""

# ruff: noqa: E402, RUF001, RUF002  (the backend joins sys.path first; the texts are Russian)

import argparse
import asyncio
import platform
import sys
import uuid
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import Settings
from app.contracts.llm import LlmCallCtx, ModelFamily
from app.contracts.web import WebSearchQuery
from app.core import time
from app.core.errors import GatewayError
from app.core.logging import configure_logging
from app.domains.instruments.mapping import logo_base, logo_cdn_url
from app.domains.media.router import LOGO_SIZES
from app.gateways.disclosure.edisclosure.adapter import EDisclosure
from app.gateways.fetch.safe_httpx import SafeHttpxFetch
from app.gateways.files.local import LocalFiles
from app.gateways.llm.gate import InProcessPriorityGate
from app.gateways.llm.gigachat import GigaChatLlm
from app.gateways.llm.metering import Metering
from app.gateways.tinvest.real import RealTInvest
from app.gateways.web.tavily import TavilyWebSearch

SBER_CARD, SBER_INN = 3043, "7707083893"  # e-disclosure card and INN of PJSC Sberbank
# Three shares of the main board: the logo URL of §8.2 is checked on them (S1-11 AC 6).
LOGO_TICKERS, LOGO_BOARD = ("SBER", "GAZP", "LKOH"), "TQBR"
WINDOWS = (32_000, 128_000)
FILLER = "Портфель инвестора состоит из акций, облигаций и фондов, доходность считается по свечам. "
RULES = (
    "Правило ассистента: числа берутся только из результатов инструментов, таблицы и графики "
    "строит код, каждое утверждение из источника сопровождается ссылкой. "
) * 60  # a stable prefix of about two thousand tokens for the prompt cache
ASK_FOR_A_FUNCTION = [
    SystemMessage("Ты помощник инвестора. Данные портфеля бери только из функций."),
    HumanMessage("Что лежит на счёте acc1?"),
]


@tool
def get_portfolio(account: str) -> str:
    """Возвращает состав портфеля пользователя на счёте с алиасом, например acc1."""
    return "SBER 400"


class Unrecorded(Metering):
    """Metering for a run without the database: the calls happen, nothing gets written."""

    async def _record(self, *args: Any) -> None:
        return None


@dataclass
class Smoke:
    settings: Settings
    metering: Metering
    llm: GigaChatLlm
    checks: list[tuple[str, str, str]] = field(default_factory=list)
    without_tools: set[ModelFamily] = field(default_factory=set)
    windows: dict[ModelFamily, int] = field(default_factory=dict)

    def ctx(self, family: ModelFamily, session_id: str | None = None) -> LlmCallCtx:
        return LlmCallCtx(
            purpose="other",
            priority="interactive",
            family=family,
            model_id=self.settings.LLM_MODELS[family],
            session_id=session_id,
        )

    async def ask(self, family: ModelFamily, messages: list[BaseMessage], **bound: Any) -> Any:
        model = self.llm.chat_model(self.settings.LLM_MODELS[family], streaming=False)
        runnable = model.bind_tools(**bound) if "tools" in bound else model.bind(**bound)
        return await self.metering.invoke(runnable, messages, ctx=self.ctx(family))

    async def check(self, name: str, step: Callable[[], Awaitable[tuple[str, str]]]) -> None:
        say(f"…        {name}")
        try:
            status, detail = await step()
        except Exception as error:  # one failed check must not stop the others
            status, detail = "ошибка", describe(error)
        self.checks.append((name, status, detail))
        say(f"{status:>8}  {name}: {detail}")


def say(line: str) -> None:
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def describe(error: BaseException) -> str:
    """The error without secrets: our code, or the type and the answer of the API."""
    if isinstance(error, GatewayError):
        cause = f"; {describe(error.__cause__)}" if error.__cause__ is not None else ""
        return f"{type(error).__name__}({error.code}){cause}"
    return f"{type(error).__name__}: {str(error)[:300]}"


def load_settings() -> Settings:
    files = [path for path in (ROOT / ".env", BACKEND / ".env") if path.exists()]
    settings = Settings(_env_file=files or None)
    updates: dict[str, Any] = {}
    # The defaults point into the API image; a run on a workstation uses the repo instead.
    if "DATA_DIR" not in settings.model_fields_set:
        updates["DATA_DIR"] = ROOT / ".smoke"
    if not settings.GIGACHAT_CA_BUNDLE.exists():
        updates["GIGACHAT_CA_BUNDLE"] = ROOT / "infra" / "certs" / "russian_trusted_root_ca.pem"
    return settings.model_copy(update=updates)


async def gigachat(smoke: Smoke, probe_windows: bool) -> None:
    s = smoke.settings
    if not s.GIGACHAT_CREDENTIALS.get_secret_value():
        smoke.checks.append(("GigaChat", "пропуск", "нет GIGACHAT_CREDENTIALS (L-01)"))
        return

    async def models() -> tuple[str, str]:
        found = await smoke.llm.list_models()
        missing = [m for m in s.LLM_MODELS.values() if m not in found]
        detail = f"OAuth прошёл, моделей {len(found)}: {', '.join(found)}"
        if missing:
            return "нет", f"{detail}; нет в списке: {', '.join(missing)}"
        return "ok", detail

    await smoke.check("GigaChat: OAuth и список моделей", models)
    for family in s.LLM_MODELS:

        async def function(family: ModelFamily = family) -> tuple[str, str]:
            answer = await smoke.ask(family, ASK_FOR_A_FUNCTION, tools=[get_portfolio])
            if answer.tool_calls:
                call = answer.tool_calls[0]
                return "ok", f"вызвана {call['name']}({call['args']})"
            smoke.without_tools.add(family)
            return "нет", f"ответ без функции: {answer.text[:120]!r}"

        await smoke.check(f"GigaChat: вызов функции, {family} ({s.LLM_MODELS[family]})", function)

    async def prompt_cache() -> tuple[str, str]:
        session, model_id = f"smoke-{uuid.uuid4()}", s.LLM_MODELS["lite"]
        model = smoke.llm.chat_model(model_id, streaming=False)
        cached = []
        for word in ("да", "нет"):
            messages = [SystemMessage(RULES), HumanMessage(f"Ответь одним словом: {word}.")]
            answer = await smoke.metering.invoke(model, messages, ctx=smoke.ctx("lite", session))
            usage = answer.usage_metadata
            details = usage.get("input_token_details") if usage else None
            cached.append(details.get("cache_read", 0) if details else 0)
        detail = f"precached_prompt_tokens: первый вызов {cached[0]}, второй {cached[1]}"
        return ("ok" if cached[1] > 0 else "нет"), detail

    await smoke.check("GigaChat: кэш префикса по X-Session-ID", prompt_cache)
    if not probe_windows:
        return
    for family in s.LLM_MODELS:

        async def window(family: ModelFamily = family) -> tuple[str, str]:
            model_id = s.LLM_MODELS[family]
            [per_piece] = await smoke.llm.count_tokens([FILLER * 20], model_id)
            accepted, refusal = 0, ""
            for size in WINDOWS:
                prompt = FILLER * int(size * 0.95 * 20 / per_piece)  # a little under the size
                try:
                    await smoke.ask(family, [HumanMessage(prompt + "\nОтветь: ок.")], max_tokens=1)
                except GatewayError as error:
                    refusal = describe(error)  # the answer of the API may name the limit
                    break
                accepted = size
            smoke.windows[family] = accepted
            detail = f"принят запрос около {accepted} токенов" if accepted else "32k не принят"
            if refusal:
                detail += f"; дальше отказ: {refusal}"
            return ("ok" if accepted else "нет"), detail

        await smoke.check(f"GigaChat: окно контекста, {family}", window)


async def tinvest(smoke: Smoke) -> None:
    token = smoke.settings.TINVEST_SYSTEM_TOKEN
    if not token.get_secret_value():
        smoke.checks.append(("T-Invest: GetAccounts", "пропуск", "нет TINVEST_SYSTEM_TOKEN (L-05)"))
        return

    async def accounts() -> tuple[str, str]:
        adapter = RealTInvest(smoke.settings)
        try:
            found = await adapter.get_accounts(token)
        finally:
            await adapter.aclose()
        levels = Counter(a.access_level for a in found)
        kinds = Counter(a.type for a in found)
        detail = f"счетов {len(found)}; access_level: {dict(levels)}; типы: {dict(kinds)}"
        # The system token reads only (AD-10).
        return ("ok" if found and set(levels) == {"read_only"} else "нет"), detail

    await smoke.check("T-Invest: GetAccounts и access_level", accounts)

    async def logos() -> tuple[str, str]:
        adapter, fetch = RealTInvest(smoke.settings), SafeHttpxFetch()
        found: list[str] = []
        failed: list[str] = []
        try:
            for ticker in LOGO_TICKERS:
                # Every hit costs a GetInstrumentBy: ten are plenty for an exact ticker.
                hits = await adapter.find_instruments(token, ticker, limit=10)
                hit = next(
                    (h for h in hits if (h.ticker, h.class_code) == (ticker, LOGO_BOARD)), None
                )
                if hit is None:
                    seen = ", ".join(f"{h.ticker}/{h.class_code}" for h in hits[:5]) or "пусто"
                    failed.append(f"{ticker}: нет {ticker}/{LOGO_BOARD} в поиске, первые: {seen}")
                    continue
                instrument = await adapter.get_instrument(token, hit.uid)
                base = logo_base(instrument.logo_name)
                if base is None:
                    failed.append(f"{ticker}: logo_name {instrument.logo_name!r}")
                    continue
                for size in LOGO_SIZES:
                    url = logo_cdn_url(base, size)
                    try:
                        image = await fetch.fetch_image(
                            url, max_bytes=smoke.settings.MEDIA_MAX_BYTES
                        )
                    except GatewayError as error:
                        failed.append(f"{url}: {error.code}")
                        continue
                    if image.content_type != "image/png":
                        failed.append(f"{url}: {image.content_type}")
                found.append(
                    f"{ticker} {instrument.logo_name} → {logo_cdn_url(base, LOGO_SIZES[0])}"
                )
        finally:
            await fetch.aclose()
            await adapter.aclose()
        detail = "; ".join(found + failed)
        return ("ok" if not failed else "нет"), detail

    await smoke.check("T-Invest: логотипы на CDN, размеры 160, 320 и 640", logos)


async def tavily(smoke: Smoke) -> None:
    if not smoke.settings.TAVILY_API_KEY.get_secret_value():
        smoke.checks.append(("Tavily: поиск", "пропуск", "нет TAVILY_API_KEY (L-02)"))
        return

    async def search() -> tuple[str, str]:
        web = TavilyWebSearch(smoke.settings)
        query = WebSearchQuery(
            query="индекс Мосбиржи новости",
            topic="news",
            depth="basic",
            time_range="week",
            max_results=3,
            include_domains=[],
            exclude_domains=[],
            include_images=False,
        )
        try:
            found = await web.search(query)
        finally:
            await web.aclose()
        detail = f"результатов {len(found.hits)}, кредитов {found.credits}"
        return ("ok" if found.hits else "нет"), detail

    await smoke.check("Tavily: поиск", search)


async def edisclosure(smoke: Smoke) -> None:
    async def card() -> tuple[str, str]:
        settings = smoke.settings
        adapter = EDisclosure(settings, LocalFiles(settings.DATA_DIR))
        try:
            found = await adapter.get_company(SBER_CARD)
        finally:
            await adapter.aclose()
        detail = f"{found.short_name}, ИНН {found.inn}; robots.txt прочитан, капчи не было"
        return ("ok" if found.inn == SBER_INN else "нет"), detail

    await smoke.check(f"e-disclosure: карточка {SBER_CARD} через Firefox", card)


def report(smoke: Smoke, probe_windows: bool) -> str:
    now = time.now().astimezone(time.MSK)
    s = smoke.settings
    windows = (
        ",".join(f"{f}:{smoke.windows.get(f) or s.LLM_CONTEXT_TOKENS[f]}" for f in s.LLM_MODELS)
        if probe_windows
        else "не проверялось (--skip-context)"
    )
    rows = [
        f"| {name} | {status} | {detail.replace('|', '/')} |"
        for name, status, detail in smoke.checks
    ]
    return "\n".join(
        [
            f"# Smoke внешних API: {now:%d.%m.%Y}",
            "",
            f"Запуск `just smoke-external` {now:%d.%m.%Y в %H:%M} МСК на {platform.system()}. "
            "Отчёт пишет `scripts/smoke_external.py` (S1-09, tech.md §15.4).",
            "",
            "| Проверка | Итог | Подробности |",
            "|---|---|---|",
            *rows,
            "",
            "## Значения для .env",
            "",
            "Семейства без вызова функций и принятые окна контекста (окно: самая длинная",
            "проба, которую API принял).",
            "",
            "```",
            f"LLM_TOOLS_UNSUPPORTED={','.join(sorted(smoke.without_tools))}",
            f"LLM_CONTEXT_TOKENS={windows}",
            "```",
            "",
        ]
    )


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--skip-context", action="store_true", help="no context window probes")
    args = parser.parse_args()
    probe_windows = not args.skip_context
    configure_logging("WARNING")
    settings = load_settings()

    engine = create_async_engine(settings.DATABASE_URL.get_secret_value())
    metering = Metering
    try:
        async with engine.connect() as conn:
            await conn.execute(text("select 1 from llm_calls limit 1"))
    except Exception as error:  # no database: the calls just go unrecorded
        say(f"база недоступна ({type(error).__name__}): вызовы не попадут в llm_calls")
        metering = Unrecorded
    gate = InProcessPriorityGate(settings.LLM_MAX_CONCURRENCY, settings.LLM_QUEUE_TIMEOUT_S)
    smoke = Smoke(settings, metering(gate, lambda: engine, settings), GigaChatLlm(settings))
    try:
        await gigachat(smoke, probe_windows)
        await tinvest(smoke)
        await tavily(smoke)
        await edisclosure(smoke)
    finally:
        await engine.dispose()

    out = ROOT / "docs" / "sources" / f"smoke-{time.msk_day():%Y-%m-%d}.md"
    out.write_text(report(smoke, probe_windows), encoding="utf-8", newline="\n")
    say(f"отчёт: {out.relative_to(ROOT)}")
    return 0 if all(status in {"ok", "пропуск"} for _, status, _ in smoke.checks) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
