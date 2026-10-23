"""classify_rules (F-05 AC 1; tech.md §9.3): keywords by intent, tickers by the regex checked
against the reference of instruments, signs of complexity, the period and the output.

The reference is seed/tinvest/instruments.yaml, the labels are classify_cases.yaml."""

# ruff: noqa: RUF001  (Russian test data)

from pathlib import Path
from typing import get_args

import pytest
from langchain_gigachat.utils.function_calling import gigachat_fix_schema

from app.contracts.agent import Intent, TaskProfile
from app.domains.agent.classify import CONFIDENT, FUNCTION, classify_rules, lexicon, profile_of
from app.gateways.fixtures import SEED, read_yaml

CASES = read_yaml(Path(__file__).parent / "classify_cases.yaml")
LEXICON = lexicon(
    (row["ticker"], row["name"]) for row in read_yaml(SEED / "tinvest" / "instruments.yaml")
)


def test_the_rules_know_nine_questions_in_ten_and_leave_the_rest_to_lite() -> None:
    sure: list[tuple[str, Intent, Intent]] = []
    for case in CASES:
        found = classify_rules(case["text"], LEXICON)
        if found is not None and found.confidence >= CONFIDENT:
            sure.append((case["text"], found.intent, case["intent"]))

    wrong = [(text, got) for text, got, expected in sure if got != expected]
    assert len(CASES) == 60
    assert wrong == []  # a doubtful question goes to Lite instead
    assert len(sure) >= 0.9 * len(CASES)


def test_the_questions_of_the_chat_tests_need_no_model_to_classify() -> None:
    # F-03 tests and e2e ask these: the run makes one call of the model, the answer.
    for text in ("Что такое дюрация облигации?", "Как устроен купон облигации?"):
        found = classify_rules(text, LEXICON)

        assert found is not None and found.confidence >= CONFIDENT
        assert found.intent == "other"


def test_a_ticker_counts_only_when_the_reference_knows_it() -> None:
    found = classify_rules("Сравни SBER, ABCD и GAZP", LEXICON)

    assert found is not None
    assert found.instruments == ["SBER", "GAZP"]


def test_a_name_of_the_reference_counts_in_its_case_forms() -> None:
    found = classify_rules("Что думают аналитики о Норильском никеле и Газпромнефти?", LEXICON)

    assert found is not None
    # Газпромнефть is another company than Газпром.
    assert found.instruments == ["Норильском никеле"]


def test_at_most_five_instruments_are_kept() -> None:
    found = classify_rules("Сравни SBER, GAZP, LKOH, ROSN, NVTK и TATN", LEXICON)

    assert found is not None
    assert found.instruments == ["SBER", "GAZP", "LKOH", "ROSN", "NVTK"]


@pytest.mark.parametrize(
    ("text", "complexity"),
    [
        ("Сравни SBER и GAZP", "medium"),
        ("Сравни SBER, GAZP и LKOH", "high"),
        ("Какая выручка у ЛУКОЙЛа за 5 лет?", "high"),
        ("Подробно расскажи про акции Северстали", "high"),
        ("Сколько стоит SBER?", "low"),
    ],
)
def test_complexity_grows_with_instruments_and_words(text: str, complexity: str) -> None:
    found = classify_rules(text, LEXICON)

    assert found is not None
    assert found.complexity == complexity


@pytest.mark.parametrize(
    ("text", "period"),
    [
        ("Покажи график цены Яндекса за год", "1y"),
        ("Доходность SBER с начала года", "ytd"),
        ("Какая выручка у ЛУКОЙЛа за 5 лет?", "5y"),
        ("Котировки GAZP за полгода", "6m"),
        ("Цена VTBR за 3 месяца", "3m"),
        ("Сравни SBER и GAZP за 3 года", "3y"),
        ("График TMOS за месяц", "1m"),
        ("Котировки LKOH за всё время", "max"),
        ("Сколько стоит SBER?", None),
    ],
)
def test_the_period_of_the_question(text: str, period: str | None) -> None:
    found = classify_rules(text, LEXICON)

    assert found is not None
    assert found.period == period


@pytest.mark.parametrize(
    ("text", "output"),
    [
        ("Покажи график цены Яндекса за год", "chart"),
        ("Покажи таблицу моих акций по стоимости", "table"),
        ("Сделай подробный разбор компании Сбербанк", "report"),
        ("Что такое дюрация облигации?", "text"),
    ],
)
def test_the_output_the_question_asks_for(text: str, output: str) -> None:
    found = classify_rules(text, LEXICON)

    assert found is not None
    assert found.output == output


def test_the_needs_name_the_data_beyond_the_intent() -> None:
    found = classify_rules("Покажи мои позиции и посчитай долю акций", LEXICON)

    assert found is not None
    assert found.intent == "portfolio_status"
    assert set(found.needs) >= {"portfolio", "calc"}


def test_a_greeting_before_a_question_leaves_the_question() -> None:
    found = classify_rules("Привет! Что у меня в портфеле?", LEXICON)

    assert found is not None
    assert (found.intent, found.source) == ("portfolio_status", "rules")


def test_a_question_without_signs_is_left_to_lite() -> None:
    found = classify_rules("Какая погода в Москве?", LEXICON)

    assert found is None or found.confidence < CONFIDENT


def test_the_function_of_lite_passes_the_schema_rules_of_gigachat() -> None:
    # langchain-gigachat refuses anyOf, which Pydantic writes for every optional field.
    parameters = FUNCTION["function"]["parameters"]

    assert gigachat_fix_schema(parameters) == parameters
    fields = set(TaskProfile.model_fields) - {"source"}
    assert set(parameters["properties"]) == fields
    assert parameters["properties"]["intent"]["enum"] == list(get_args(Intent.__value__))


def test_a_call_of_lite_becomes_a_profile_of_the_model() -> None:
    found = profile_of(
        {
            "intent": "compare",
            "complexity": "high",
            "needs": ["market", "astrology", "market"],
            "output": "chart",
            "instruments": ["A", "B", "C", "D", "E", "F"],
            "period": "2w",
            "confidence": 1.4,
            "source": "rules",
            "comment": "лишнее поле",
        }
    )

    assert found == TaskProfile(
        intent="compare",
        complexity="high",
        needs=["market"],
        output="chart",
        instruments=["A", "B", "C", "D", "E"],
        period=None,
        confidence=1,
        source="llm",
    )


@pytest.mark.parametrize(
    "args",
    [
        {},
        {"intent": "weather", "complexity": "low", "needs": [], "output": "text"},
        {"intent": "news", "complexity": "huge", "needs": [], "output": "text"},
    ],
)
def test_a_call_the_contract_refuses_gives_no_profile(args: dict[str, object]) -> None:
    assert profile_of(args) is None
