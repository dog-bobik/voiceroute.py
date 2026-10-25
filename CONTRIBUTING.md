# Участие в разработке

## Ветки

Используйте общепринятые префиксы:

- `feature/` — новая функциональность;
- `fix/` — исправление ошибки;
- `docs/` — документация;
- `refactor/` — внутреннее изменение без нового поведения;
- `test/` — тесты;
- `chore/` — инфраструктура и обслуживание;
- `release/` — подготовка выпуска;
- `hotfix/` — срочное исправление стабильной версии.

Ветки с префиксом `codex/` запрещены.

## Коммиты

Сообщения пишутся на английском языке в формате Conventional Commits со scope:

```text
feat(events): add resumable channel stream
fix(http): preserve idempotency key across retries
docs(readme): document development setup
```

## Слияния

- изменения попадают в `main` через pull request;
- fast-forward merge запрещён;
- используйте merge commit (`git merge --no-ff`);
- перед слиянием должны пройти lint, format, type check и tests;
- публичное поведение сопровождается тестами и документацией;
- несовместимые изменения до `1.0.0` явно отмечаются в changelog.

## Локальная проверка

```bash
ruff check .
ruff format --check .
mypy src
pytest
```

