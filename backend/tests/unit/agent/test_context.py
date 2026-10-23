"""What the model reads on each step (tech.md §9.6, §9.12, §3.5): the static system prompt first
and alone, the history in turns, then the context of the service and the question."""

# ruff: noqa: RUF001  (Russian test data)

from datetime import UTC, date, datetime

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.contracts.api.broker import BrokerAccountOut, BrokerConnectionOut
from app.domains.agent.context import (
    Said,
    context_block,
    history_messages,
    history_text,
    llm_messages,
    system_prompt,
)

# 21:15 UTC is 00:15 of the next day in Moscow.
LATE_EVENING = datetime(2026, 10, 22, 21, 15, tzinfo=UTC)


def account(alias: str, name: str, *, hidden: bool = False) -> BrokerAccountOut:
    return BrokerAccountOut(
        alias=alias,
        name=name,
        type="broker",
        status="open",
        opened_at=date(2024, 1, 10),
        is_hidden=hidden,
    )


def broker(*accounts: BrokerAccountOut) -> BrokerConnectionOut:
    return BrokerConnectionOut(
        connected=True,
        status="active",
        token_hint="Fx7k",
        last_verified_at=LATE_EVENING,
        accounts=list(accounts),
    )


NO_BROKER = BrokerConnectionOut(
    connected=False, status=None, token_hint=None, last_verified_at=None, accounts=[]
)


def test_the_system_prompt_keeps_the_rules_and_drops_the_file_header() -> None:
    prompt = system_prompt()

    assert not prompt.startswith("<!--")
    assert "<<<EXTERNAL" in prompt  # rule 5 of §9.6
    assert "[[c1]]" in prompt  # rule 3: placeholders on their own line
    assert "[s1]" in prompt  # rule 4: citations


def test_the_static_prompt_opens_the_context_alone_and_the_question_closes_it() -> None:
    history = [HumanMessage("Что такое купон?"), AIMessage("Купон: процентный доход.")]

    messages = llm_messages(None, history, "Контекст сервиса", "А дюрация?")

    assert isinstance(messages[0], SystemMessage)
    assert messages[0].content == system_prompt()
    assert [type(m) for m in messages[1:]] == [HumanMessage, AIMessage, HumanMessage]
    assert sum(isinstance(m, SystemMessage) for m in messages) == 1
    last = messages[-1].content
    assert isinstance(last, str)
    assert last.startswith("Контекст сервиса") and last.endswith("А дюрация?")


def test_the_summary_of_the_thread_follows_the_static_prompt() -> None:
    messages = llm_messages("Говорили о ВДО.", [], "Контекст", "Что дальше?")

    content = messages[0].content
    assert isinstance(content, str)
    assert content.startswith(system_prompt()) and content.endswith("Говорили о ВДО.")


def test_the_block_tells_moscow_time_accounts_by_name_and_the_style() -> None:
    block = context_block(
        LATE_EVENING,
        broker(account("acc1", "Брокерский счёт"), account("acc2", "ИИС")),
        "concise",
    )

    assert "23.10.2026, 00:15 МСК" in block
    assert "пятница" in block
    assert "acc1 «Брокерский счёт»" in block and "acc2 «ИИС»" in block
    assert "кратко" in block


def test_hidden_accounts_stay_out_of_the_block() -> None:
    block = context_block(
        LATE_EVENING,
        broker(account("acc1", "Брокерский счёт"), account("acc2", "Старый ИИС", hidden=True)),
        "detailed",
    )

    assert "acc1 «Брокерский счёт»" in block
    assert "acc2" not in block and "Старый ИИС" not in block
    assert "подробно" in block


def test_the_block_says_when_the_broker_is_missing_or_its_token_refused() -> None:
    refused = broker(account("acc1", "Брокерский счёт")).model_copy(update={"status": "invalid"})

    missing = context_block(LATE_EVENING, NO_BROKER, "concise")
    invalid = context_block(LATE_EVENING, refused, "concise")

    assert "не подключён" in missing and "Настройк" in missing
    assert "не действует" in invalid and "acc1" not in invalid


def test_history_keeps_the_last_turns_and_drops_unanswered_questions() -> None:
    said = [
        Said("user", "complete", "Первый вопрос"),
        Said("assistant", "complete", "Первый ответ"),
        Said("user", "complete", "Вопрос без ответа"),
        Said("assistant", "failed", ""),
        Said("user", "complete", "Второй вопрос"),
        Said("assistant", "partial", "Начало второго ответа"),
        Said("user", "complete", "Прерванный вопрос"),
    ]

    full = history_messages(said, limit=8)
    short = history_messages(said, limit=3)

    assert [(type(m), m.content) for m in full] == [
        (HumanMessage, "Первый вопрос"),
        (AIMessage, "Первый ответ"),
        (HumanMessage, "Второй вопрос"),
        (AIMessage, "Начало второго ответа"),
    ]
    # The window starts with a question, so turns keep alternating.
    assert [m.content for m in short] == ["Второй вопрос", "Начало второго ответа"]


def test_history_names_artifacts_in_place_of_their_placeholders() -> None:
    labels = {"c1": "[график «Структура»]", "t1": "[таблица «Позиции»]"}

    text = history_text("Итог.\n\n[[c1]]\n\nДетали:\n  [[t1]]\n[[c9]]\nКонец.", labels)

    assert text == "Итог.\n\n[график «Структура»]\n\nДетали:\n[таблица «Позиции»]\nКонец."
