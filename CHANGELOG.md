# История изменений

Проект следует [Semantic Versioning](https://semver.org/) и рекомендациям
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added

- Начальная структура Python-пакета.
- Асинхронный HTTP transport и bot-аутентификация.
- Базовые модели и API профиля текущего бота.
- Восстанавливаемые SSE-потоки с checkpoint после успешной обработки.
- Атомарное файловое и process-local хранилища cursor.
- Общий sliding-window rate limiter и безопасные retry с учётом `Retry-After`.
- Постраничное восстановление backlog перед переходом к live SSE.
- Публичный `EventTransport` и `LegacySSETransport`, отделяющие runtime от сетевого
  протокола событий.
- Независимые `Command`, `CommandRegistry`, `CommandInvocation` и
  `PrefixCommandAdapter` с aliases, группами, типизированными аргументами и command
  lifecycle events.
- Command pipeline с async middleware, checks, cooldowns и concurrency limits.
- Расширения с декларативными командами/listeners, атомарной регистрацией и module
  load/unload/reload lifecycle.
- Явный runtime lifecycle, graceful shutdown и независимый supervision channel consumers.

