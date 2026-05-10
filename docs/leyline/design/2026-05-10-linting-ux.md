# Добавление линтинга - UX spec
Date: 2026-05-10
Product spec: docs/leyline/specs/2026-05-10-linting-design.md
Surfaces: developer-facing

## Public API surface enumeration
- `make lint` - цель Makefile для запуска линтера
- `make test` - расширенная цель, включающая линтинг перед тестами
- `ruff check .` - прямая команда для проверки кода
- `ruff format --check .` - проверка форматирования

## Error shapes and failure-mode contracts
- Формат: `path/to/file.py:<line>:<col>: <code> <message>`
- Коды ошибок: стандартные коды ruff (E, F, W, I, etc.)
- Группировка по файлам для удобства чтения

## Log / output schema
```
aws_sso_autologin/file.py:42:5: E501 Line too long (89 > 88 characters)
Found 1 error.
```

При успехе:
```
All checks passed!
```

## Exit-code semantics
- 0: Проверка пройдена успешно, ошибок не найдено
- 1: Найдены ошибки линтинга
- 2: Ошибка при запуске линтера (неправильная конфигурация, отсутствие файлов)

## Telemetry-label conventions
- Не применимо для данной задачи

## Documented failure modes

### Ошибка: ruff не установлен
**Когда:** При вызове `make lint` без установленных dev-зависимостей
**Что видит пользователь:**
```
make: ruff: Command not found
make: *** [Makefile:46: lint] Error 127
```
**Recovery:** Запустить `make prepare-dev`

### Ошибка: Найдены стилистические проблемы
**Когда:** Код не соответствует правилам ruff
**Что видит пользователь:**
```
aws_sso_autologin/service.py:150:89: E501 Line too long (95 > 88 characters)
aws_sso_autologin/tray.py:45:1: I001 Import block is un-sorted
Found 2 errors.
make: *** [Makefile:46: lint] Error 1
```
**Recovery:** Запустить `ruff check . --fix` для автоматического исправления или исправить вручную

## Voice and tone in error messages

### Error:
```
aws_sso_autologin/cli.py:23:5: F841 Local variable `config` is assigned but never used
```
Тон: Технический, точный, без лишней эмоциональности

### Success:
```
All checks passed!
```
Тон: Краткий, позитивный, завершенный

### Progress/Info:
```
Running linter...
Checking aws_sso_autologin/aws.py
Checking aws_sso_autologin/tray.py
...
All checks passed!
```
Тон: Информативный, показывает прогресс

## Non-goals
- Создание собственных правил линтинга
- Интеграция с IDE (это делается через плагины IDE)
- Автоматическое исправление при pre-commit (out of scope)
- Проверка типов (type checking - отдельная задача)

UX spec approved - round 1 - 2026-05-10

design-interrogation skipped - scope: developer-facing surface with simple CLI output, non-complex error paths - 2026-05-10
