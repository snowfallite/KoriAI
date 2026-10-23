"""Invariants of classify_rules (tech.md §9.3, §11): it never raises, gives the same profile for
the same text, and a profile it gives is of the rules, keeps at most five instruments and takes
each of them from the text."""

from hypothesis import given
from hypothesis import strategies as st

from app.domains.agent.classify import Lexicon, classify_rules, lexicon

WORDS = [
    "портфель",
    "моих",
    "акций",
    "почему",
    "сравни",
    "выручка",
    "новости",
    "график",
    "цена",
    "курс",
    "доллара",
    "привет",
    "что такое",
    "за 5 лет",
    "подробный разбор",
    "SBER",
    "GAZP",
    "Газпрома",
    "ЛУКОЙЛ",
    "Норильского никеля",
]
tickers = st.from_regex(r"[A-Z]{3,6}", fullmatch=True)
names = st.text(alphabet="абвгдеёжзиклмнопрстуфхцчшщыэюя -0123", min_size=1, max_size=20)
lexicons = st.lists(st.tuples(tickers, names), max_size=8).map(lexicon)
any_text = st.text(alphabet=st.characters(blacklist_categories=["Cs"]), max_size=120)
mixed = st.lists(st.sampled_from(WORDS) | any_text, max_size=8).map(" ".join)
texts = any_text | mixed


@given(texts, lexicons)
def test_the_rules_never_raise_and_repeat_themselves(text: str, known: Lexicon) -> None:
    assert classify_rules(text, known) == classify_rules(text, known)


@given(texts, lexicons)
def test_a_profile_of_the_rules_keeps_its_instruments_from_the_text(
    text: str, known: Lexicon
) -> None:
    found = classify_rules(text, known)

    if found is not None:
        assert found.source == "rules"
        assert 0 <= found.confidence <= 1
        assert len(found.instruments) <= 5
        assert all(mention in text for mention in found.instruments)
