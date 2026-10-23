"""The profile of a question (tech.md §9.3): classify_rules reads it from keywords and the
reference of instruments, without IO and without exceptions. A profile below CONFIDENT, or none,
goes to Lite, which answers with the function task_profile (FUNCTION, profile_of).
"""

# ruff: noqa: RUF001  (Russian keywords: many of their letters look like Latin ones)

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, get_args

from pydantic import ValidationError

from app.contracts.agent import Intent, Need, TaskProfile
from app.contracts.common import PeriodCode

type Complexity = Literal["low", "medium", "high"]
type Output = Literal["text", "table", "chart", "report"]

CONFIDENT = 0.8  # a profile below it goes to Lite (§9.1)
MAX_INSTRUMENTS = 5
FALLBACK = TaskProfile(
    intent="other",
    complexity="low",
    needs=[],
    output="text",
    instruments=[],
    period=None,
    confidence=0,
    source="rules",
)

INTENTS: list[str] = list(get_args(Intent.__value__))
NEEDS: list[Need] = list(get_args(Need.__value__))
PERIODS: list[str] = list(get_args(PeriodCode.__value__))


def _any(*patterns: str) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{pattern})" for pattern in patterns))


# Patterns read the plain text: lower case, the letter yo folded into ye, single spaces.
GREETINGS = ("привет", "приветик", "здравствуй", "здравствуйте", "здрасте", "хай", "салют")
DAYTIME = ("добрый", "доброе", "доброй", "день", "вечер", "утро", "ночи")
THANKS = ("спасибо", "спасибочки", "благодарю", "спс", "большое")
GOODBYES = ("пока", "до", "свидания", "завтра", "встречи")
CHATTER = ("как", "дела", "ты", "поживаешь", "ок", "окей", "ага", "угу", "да", "нет")
ASSENT = ("понятно", "ясно", "отлично", "супер", "круто", "хорошо", "все", "понял", "поняла")
SMALLTALK = frozenset((*GREETINGS, *DAYTIME, *THANKS, *GOODBYES, *CHATTER, *ASSENT))
GREETING = re.compile(
    r"^(?:привет\w*|здравствуй\w*|здрасте|добр(?:ый|ое|ой) (?:день|вечер|утро|ночи)|хай|салют)"
    r"[\s,.!]*"
)
HELP = _any(
    r"\b(?:что|чем) (?:ты |вы )?(?:умеешь|умеете|можешь|можете|делаешь|занимаешься)",
    r"\bкто ты\b|\bты кто\b|твои возможност|какие у тебя возможност",
    r"как (?:тобой |этим |сервисом |чатом |ботом )?(?:пользоваться|использовать)",
    r"\bтокен\w*",
    r"откуда (?:ты )?(?:берешь|берете|берутся|данные|информаци)",
    r"какие (?:вопросы|задачи) (?:тебе|можно|ты)|что (?:тебя )?можно (?:спросить|спрашивать)",
    r"как (?:работает|устроен) (?:этот |твой )?(?:сервис|чат|бот)",
    r"^(?:помощь|справка|help|инструкция)\W*$",
)
RESEARCH = _any(
    r"(?:подробн|полн|глубок|детальн|комплексн|развернут|фундаментальн)\w* "
    r"(?:разбор|анализ|обзор|исследовани|отчет)",
    r"всесторонн",
    r"исследовани",
    r"разбери\w* (?:компани|эмитент|бизнес)|разбор (?:компани|эмитент|бизнес)",
    r"инвестиционн\w* (?:иде|тезис|кейс)",
    r"подготовь (?:отчет|обзор|разбор|анализ)",
)
COMPARE = _any(
    r"сравн",
    r"что лучше|кто лучше|лучше ли|выгоднее",
    r"отлича|разниц",
    r"\bпротив\b|\bvs\b|versus",
    r"корреляц",
    r"\bили\b",
)
NEWS = _any(
    r"новост",
    r"что (?:пишут|говорят|случилось|произошло|происходит|нового)",
    r"событи|\bслух|заявлени|заявил|пресс-релиз|инфоповод",
)
NEWS_MOVE = re.compile(
    r"почему(?: \w+){0,3} (?:упал|вырос|подешевел|подорожал|снизил|снижа|раст[уе]т|пада|"
    r"обвалил|рухнул|просел|взлетел)"
)
EDUCATION = _any(
    r"что такое|что (?:значит|означает)|что это за",
    r"объясни",
    r"как (?:устроен|работа|рассчитыва|считает|считать|вычисля|формиру|начисля)",
    r"чем (?:\w+ ){0,3}отлича|в чем разница",
    r"(?:зачем|для чего) нуж",
    r"\bтермин|определени",
)
POSSESSIVE = re.compile(
    r"\b(?:мой|моя|мое|мои|моего|моей|моих|моим|моими|моем|мою|мне|у меня|наш|нашего|нашем|"
    r"наши|наших)\b|\bя (?:купил|продал|заплатил|получил|держу|вложил|инвестировал|заработал|"
    r"потерял)"
)
PORTFOLIO_NOUN = _any(
    r"\bсчет|\bиис\b|акци|бумаг|позици|облигац|\bфонд|сделк|операци|дивиденд|купон|доход",
    r"комисси|актив|вложени|инвестици|деньг|баланс|пополнени",
)
PORTFOLIO_ANALYSIS = _any(
    r"почему|анализ|проанализ|оцени",
    r"\bриск|доходност|просадк|волатильн|диверсифи|ребаланс|перекос|концентрац",
    r"вклад|тян(?:ет|ут)|(?:хуже|лучше) всего|отста|обгоня",
    r"результат|динамик|сравни|бенчмарк|индекс",
    r"как (?:идут|дела|себя чувству|поживает)|что с (?:\w+ )?портфел",
    r"упал|вырос|просел|снизил|подешевел|подорожал",
)
PORTFOLIO_STATUS = _any(
    r"что у меня|что в (?:\w+ )?портфел|что лежит|что есть",
    r"состав|стоит|стоимост|позици|структур|сколько|баланс",
    r"покажи|выведи|перечисли|список|таблиц",
    r"какие (?:\w+ )?(?:акции|облигации|бумаги|фонды|позиции|валют)",
    r"комисси|сделк|операци|прибыл|убыт|заработал|потерял|дивиденд|купон|доход",
)
FINANCIALS = _any(
    r"отчетност|мсфо|рсбу|\bifrs\b",
    r"выручк|прибыл|ebitda|ебитда|oibda|себестоимост",
    r"(?:чист|долгов)\w* (?:долг|нагрузк)|\bдолг",
    r"денежн\w* поток|\bfcf\b|капекс|capex|капзатрат|капитальн\w* затрат",
    r"маржинальн|рентабельн|\bмаржа",
    r"финансов\w* (?:результат|показател|отчет)|отчет\w* о (?:прибыл|финансов|движени)",
)
QUOTE = _any(
    r"сколько (?:\w+ )?сто[ия]т\b|почем\b|по чем\b",
    r"\bцен(?:а|ы|у|е|ой|ам)?\b|котировк|\bкурс",
    r"стоимост\w* (?:акци|бумаг|облигац|фонд|па)",
    r"график|динамик\w* цен|подорожал|подешевел|торгу[еюя]т",
)
ANALYSIS = _any(
    r"расскажи|что (?:думаешь|скажешь|думают)|анализ|оцени",
    r"перспектив|дивиденд|купон|выплат",
    r"мультипликатор|p/e|\bpe\b|p/b|\bpb\b|ev/ebitda",
    r"аналитик|консенсус|прогноз|рекомендац|целев\w* цен|справедлив|недооцен|переоцен",
    r"стоит ли|\bриск|фундаментал|бизнес|интересн",
    r"отчита|когда (?:\w+ )?(?:отчет|выплат)",
)
CURRENCY = re.compile(r"\b(?:доллар|евро\b|юан|рубл|валют|франк|фунт|тенге)\w*", re.IGNORECASE)
CALC = _any(
    r"посчитай|рассчитай|вычисли|подсчитай",
    r"сколько процент|в процент|\bдол(?:я|ю|и|ей)\b",
)
DOCS = _any(r"документ|презентаци|годов\w* отчет|пресс-релиз|в отчете|раскрыти")
HIGH = _any(
    r"подробн|детальн|глубок|развернут|разбор|разбер|всесторонн|комплексн",
    r"за (?:последние )?(?:5|пять|10|десять|несколько) лет",
)
CHART = _any(r"график|диаграмм|нарисуй|визуализ|динамик")
TABLE = _any(r"таблиц|список|списк|\bтоп\b|топ-\d|перечисли")
REPORT = _any(r"(?:сделай|подготовь|составь) (?:\w+ )?(?:отчет|обзор|доклад)")
LAST = r"(?:последн\w+ )?"
PERIOD_RULES: list[tuple[re.Pattern[str], PeriodCode]] = [
    (_any(r"с начала (?:этого )?года|за (?:этот|текущий) год|в этом году|\bytd\b"), "ytd"),
    (_any(rf"за {LAST}(?:5|пять) лет"), "5y"),
    (
        _any(
            rf"за {LAST}(?:10|десять|\d\d) лет",
            r"за все время|за всю историю|за весь период|с момента (?:покупки|открытия)",
        ),
        "max",
    ),
    (_any(rf"за {LAST}(?:3|три) (?:года|лет)"), "3y"),
    (_any(rf"за {LAST}(?:6|шесть) месяц", r"за пол ?года|полугоди"), "6m"),
    (_any(rf"за {LAST}(?:3|три) месяц", rf"за {LAST}квартал"), "3m"),
    (_any(rf"за {LAST}(?:12 месяц|год)\b", r"за (?:1|один) год\b"), "1y"),
    (_any(rf"за {LAST}(?:1 |один )?месяц\b", r"за 30 дней"), "1m"),
]

TOKEN = re.compile(r"[0-9A-Za-zА-Яа-яЁё]+")
TICKER = re.compile(r"\b[A-Z]{3,6}\b")
ADJECTIVE = ("ого", "его", "ому", "ему", "ыми", "ими", "ий", "ый", "ой", "ая", "яя", "ое")
VOWELS = "аеиоуыэюяьй"
EXTRA = 3  # letters of a case ending a name may take


def _plain(text: str) -> str:
    return " ".join(text.lower().replace("ё", "е").split())


def _core(word: str) -> str:
    """A word of a name without its ending, so «Норильского никеля» meets «Норильский никель»."""
    if len(word) <= 4 or any(char.isdigit() for char in word):
        return word
    for ending in ADJECTIVE:
        if word.endswith(ending) and len(word) - len(ending) >= 4:
            return word[: -len(ending)]
    return word[:-1] if word[-1] in VOWELS else word


@dataclass(frozen=True, slots=True)
class _Name:
    ticker: str
    cores: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Lexicon:
    """What the rules know of the reference of instruments (§9.3): the tickers and the names."""

    tickers: frozenset[str]
    names: Mapping[str, tuple[_Name, ...]] = field(default_factory=dict)  # by first letters


def lexicon(rows: Iterable[tuple[str, str]]) -> Lexicon:
    """The lexicon of (ticker, name) rows of the instruments table."""
    tickers: set[str] = set()
    names: dict[str, list[_Name]] = {}
    for ticker, name in rows:
        tickers.add(ticker)
        cores = tuple(_core(_plain(word)) for word in TOKEN.findall(name))
        if not cores or (len(cores) == 1 and len(cores[0]) < 3):
            continue  # a one-letter name would match half of the words
        names.setdefault(cores[0][:3], []).append(_Name(ticker, cores))
    return Lexicon(frozenset(tickers), {head: tuple(found) for head, found in names.items()})


def _fits(word: str, core: str) -> bool:
    if any(char.isdigit() for char in core):
        return word == core
    return word.startswith(core) and len(word) - len(core) <= EXTRA


def mentions(text: str, known: Lexicon) -> list[str]:
    """Instruments of the text as written there, in order, one per ticker, at most five."""
    found: list[tuple[int, int, str]] = [
        (m.start(), m.end(), m.group()) for m in TICKER.finditer(text) if m.group() in known.tickers
    ]
    words = list(TOKEN.finditer(text))
    plain = [_plain(word.group()) for word in words]
    for index, word in enumerate(plain):
        # A name sits under the first three letters of its first word, a shorter word whole.
        candidates = [name for size in (1, 2, 3) for name in known.names.get(word[:size], ())]
        for name in candidates:
            end = index + len(name.cores)
            if end <= len(plain) and all(
                _fits(plain[index + n], core) for n, core in enumerate(name.cores)
            ):
                found.append((words[index].start(), words[end - 1].end(), name.ticker))
                break
    kept: list[str] = []
    seen: set[str] = set()
    taken_to = -1
    for start, end, ticker in sorted(found):
        if start < taken_to or ticker in seen:
            continue
        seen.add(ticker)
        taken_to = end
        kept.append(text[start:end])
    return kept[:MAX_INSTRUMENTS]


def classify_rules(text: str, ctx: Lexicon) -> TaskProfile | None:
    """The profile of a question by keywords; None when nothing in it is known (§9.3)."""
    plain = _plain(text)
    words = TOKEN.findall(plain)
    if words and len(words) <= 6 and all(word in SMALLTALK for word in words):
        return _profile("smalltalk", 0.95, plain, [])
    plain = GREETING.sub("", plain)
    found = mentions(text, ctx)
    guess = _intent(plain, len(found))
    if guess is None:
        return None
    intent, confidence = guess
    if intent == "instrument_quote" and not found:  # a currency by its word: «курс юаня»
        quoted = CURRENCY.search(text)
        found = [quoted.group()] if quoted else []
    return _profile(intent, confidence, plain, found)


def _owned(plain: str) -> bool:
    """The question is about the user's own portfolio."""
    if "портфел" in plain or re.search(r"на (?:иис|брокерском счете)", plain):
        return True
    return bool(POSSESSIVE.search(plain) and PORTFOLIO_NOUN.search(plain))


def _intent(plain: str, count: int) -> tuple[Intent, float] | None:
    """The first rule that fits wins: the order settles questions that fit several."""
    owned = _owned(plain)
    if count == 0 and HELP.search(plain):
        return "help", 0.9
    if RESEARCH.search(plain) and not owned:
        return "research", 0.9
    if count >= 2 and COMPARE.search(plain):
        return "compare", 0.9
    if NEWS.search(plain):
        return "news", 0.9
    if count == 0 and not POSSESSIVE.search(plain) and EDUCATION.search(plain):
        return "other", 0.85
    if owned:
        if PORTFOLIO_ANALYSIS.search(plain):
            return "portfolio_analysis", 0.9
        return "portfolio_status", 0.85 if PORTFOLIO_STATUS.search(plain) else 0.7
    if FINANCIALS.search(plain):
        return "financials", 0.9 if count else 0.7
    if count == 0:
        if CURRENCY.search(plain) and QUOTE.search(plain):
            return "instrument_quote", 0.85
        return ("compare", 0.6) if COMPARE.search(plain) else None
    if NEWS_MOVE.search(plain):
        return "news", 0.85
    if count >= 2:
        return "compare", 0.7
    if QUOTE.search(plain):
        return "instrument_quote", 0.9
    return "instrument_analysis", 0.85 if ANALYSIS.search(plain) else 0.6


def _profile(intent: Intent, confidence: float, plain: str, found: list[str]) -> TaskProfile:
    return TaskProfile(
        intent=intent,
        complexity=_complexity(intent, plain, len(found)),
        needs=_needs(intent, plain, found),
        output=_output(intent, plain),
        instruments=found,
        period=next((code for pattern, code in PERIOD_RULES if pattern.search(plain)), None),
        confidence=confidence,
        source="rules",
    )


def _complexity(intent: Intent, plain: str, count: int) -> Complexity:
    if intent == "research" or count >= 3 or HIGH.search(plain):
        return "high"
    deep = {"portfolio_analysis", "instrument_analysis", "compare", "financials"}
    return "medium" if count == 2 or intent in deep else "low"


def _needs(intent: Intent, plain: str, found: list[str]) -> list[Need]:
    if intent in {"smalltalk", "help"}:
        return []
    wanted: set[Need] = set()
    if intent.startswith("portfolio") or _owned(plain):
        wanted.add("portfolio")
    if found or intent in {"instrument_quote", "instrument_analysis", "compare"}:
        wanted.add("market")
    if intent == "financials" or FINANCIALS.search(plain):
        wanted.add("disclosures")
    if DOCS.search(plain):
        wanted.add("docs")
    if intent == "news" or NEWS.search(plain) or NEWS_MOVE.search(plain):
        wanted.add("web")
    if CALC.search(plain):
        wanted.add("calc")
    return [need for need in NEEDS if need in wanted]


def _output(intent: Intent, plain: str) -> Output:
    if intent == "research" or REPORT.search(plain):
        return "report"
    if CHART.search(plain):
        return "chart"
    return "table" if TABLE.search(plain) else "text"


# Lite answers with a call of this function (§9.1). GigaChat refuses anyOf in a schema, and
# Pydantic writes one for every optional field, so the schema of TaskProfile is spelled out.
FUNCTION: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "task_profile",
        "description": "Записывает профиль вопроса пользователя: о чём он, насколько сложен, "
        "какие данные нужны для ответа и в каком виде ответить.",
        "parameters": {
            "type": "object",
            "properties": {
                "intent": {"type": "string", "enum": INTENTS, "description": "Интент вопроса"},
                "complexity": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "Сложность вопроса",
                },
                "needs": {
                    "type": "array",
                    "items": {"type": "string", "enum": NEEDS},
                    "description": "Какие данные нужны для ответа",
                },
                "output": {
                    "type": "string",
                    "enum": ["text", "table", "chart", "report"],
                    "description": "В каком виде ответить",
                },
                "instruments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Инструменты и компании так, как они написаны в вопросе",
                },
                "period": {
                    "type": "string",
                    "enum": PERIODS,
                    "description": "Период, если вопрос его называет",
                },
                "confidence": {"type": "number", "description": "Уверенность в интенте, 0..1"},
            },
            "required": ["intent", "complexity", "needs", "output", "instruments", "confidence"],
        },
        "few_shot_examples": [
            {
                "request": "Почему мой портфель упал за неделю?",
                "params": {
                    "intent": "portfolio_analysis",
                    "complexity": "medium",
                    "needs": ["portfolio", "market"],
                    "output": "text",
                    "instruments": [],
                    "confidence": 0.9,
                },
            },
            {
                "request": "Сравни выручку Газпрома и ЛУКОЙЛа за 5 лет",
                "params": {
                    "intent": "compare",
                    "complexity": "high",
                    "needs": ["market", "disclosures"],
                    "output": "chart",
                    "instruments": ["Газпрома", "ЛУКОЙЛа"],
                    "period": "5y",
                    "confidence": 0.9,
                },
            },
        ],
    },
}
FUNCTION_NAME: str = FUNCTION["function"]["name"]


def profile_of(args: Mapping[str, Any]) -> TaskProfile | None:
    """The profile in the arguments of the call of task_profile; None when the contract refuses
    its intent, complexity or output. Unknown needs and periods drop out."""
    data = {key: value for key, value in args.items() if key in TaskProfile.model_fields}
    raw_needs = data.get("needs")
    data["needs"] = [need for need in NEEDS if isinstance(raw_needs, list) and need in raw_needs]
    raw = data.get("instruments")
    named = [str(item) for item in raw] if isinstance(raw, list) else []
    data["instruments"] = named[:MAX_INSTRUMENTS]
    if data.get("period") not in PERIODS:
        data["period"] = None
    confidence = data.get("confidence")
    data["confidence"] = (
        min(max(float(confidence), 0.0), 1.0) if isinstance(confidence, (int, float)) else 0.5
    )
    try:
        return TaskProfile.model_validate({**data, "source": "llm"})
    except ValidationError:
        return None
