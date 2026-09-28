# 氷 Kōri

ИИ-аналитик для частного инвестора с брокерским счётом в Т-Инвестициях: портфель, отчётность эмитентов и новости в одном диалоге.

Источник истины: [`tech.md`](tech.md). Правила сессий нейросети: [`CLAUDE.md`](CLAUDE.md). Визуальный шаблон: [`docs/ui-references/template/`](docs/ui-references/template/).

## Требования

- [uv](https://docs.astral.sh/uv/): Python 3.13 он скачает сам.
- [pnpm](https://pnpm.io/) 10: Node 24 для проекта он скачает сам (`devEngines` в `frontend/package.json`).
- [just](https://just.systems/): `uv tool install rust-just`.
- Docker: Postgres 18 и Qdrant для интеграционных тестов и e2e.

## Команды

```sh
just setup            # зависимости и браузер Playwright
just gate core-impl   # всё, что проверяет PR-гейт; аргумент: метки PR через запятую
just --list           # остальные команды, полный список в tech.md §15.4
```

## Сертификаты НУЦ Минцифры

Индекс пакетов T-Bank (`t-tech-investments`, §4.3) подписан сертификатом Russian Trusted Sub CA и не отдаёт промежуточный сертификат. `infra/certs/russian_trusted_root_ca.pem` содержит корневой и промежуточный сертификаты НУЦ; этот же файл нужен GigaChat (L-07).

- Локально uv берёт сертификаты из системного хранилища (`native-tls` в `backend/pyproject.toml`). Если сертификатов НУЦ там нет, установите файл в хранилище или задайте `SSL_CERT_FILE` на бандл из системных корней и этого файла.
- В CI (L-04) шаг «Trust the Russian CA» склеивает такой бандл и выставляет `SSL_CERT_FILE`.

## Настройка GitHub (один раз)

Нужен [GitHub CLI](https://cli.github.com/). Защита веток в приватном репозитории требует GitHub Pro или публичного репозитория.

```sh
gh repo create <owner>/<name> --public --source . --remote origin --push
gh label create contract-change --color D93F0B --description "Контрактная зона и бамп CORE_VERSION"
gh label create core-impl --color 0E8A16 --description "Реализация текущего ядра без правки tech.md"
gh label create owner --color 5319E7 --description "Общая зона, режим владельца"
gh repo edit --enable-squash-merge --enable-merge-commit=false --enable-rebase-merge=false --delete-branch-on-merge
gh api -X PUT "repos/{owner}/{repo}/branches/main/protection" --input .github/branch-protection.json
```
