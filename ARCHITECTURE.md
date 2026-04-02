# Архитектура проекта "Ева 2.0"

## Описание проекта

«Ева 2.0» – это интеллектуальный ИИ-агент с модульной архитектурой, способный к самонаблюдению и самоизменению собственного кода. Он сочетает в себе "мозг" (ядро принятия решений и память) и внешнюю LLM-модель (например, GPT-4) для генерации идей и кода.

## Принципы архитектуры

- **Модульность**: Каждый файл соответствует отдельному "кубику" функциональности
- **Высокая связность внутри модуля, слабая связанность между модулями**
- **Принцип синапсов**: Модули общаются через четко определённые интерфейсы
- **Гибкость**: Возможность замены/обновления модулей без влияния на другие

### ⚠️ Жёсткое правило: Один файл = одна роль

**Если файл:**

- растёт >400–500 строк
- содержит 2 логически разных процесса
→ **делить без обсуждений**

**Почему это важно:**

- Чёткие входы/выходы
- Минимальные зависимости
- Возможность переподключать модули, не ломая всё
- Улучшает "синапсы" между модулями

## Структура директорий

```
Eva/
├── eva_core/          # Ядро системы ("мозг")
├── eva_code/          # Генерация и редактирование кода ("руки")
├── eva_test/          # Тестирование и песочница ("лаборатория")
├── eva_utils/         # Вспомогательные утилиты
├── eva_api/           # Интерфейс (API/CLI)
├── reflection_log/     # Журнал рефлексии
├── _docs/             # Документация
├── llm_proxy.py       # Прокси для LLM (единая точка доступа)
├── main.py            # Точка входа (или run_eva.py)
├── requirements.txt    # Зависимости
└── README.md          # Описание проекта
```

---

## eva_core/ - Ядро системы

**Назначение**: Центральные модули "мышления" и координации системы.

### Структура (согласно правилу "один файл = одна роль")

```
eva_core/
├── decision_engine.py    # только координация
├── memory_manager.py     # работа с памятью (PostgreSQL)
├── goal_handler.py       # работа с целями (планируется)
├── action_router.py      # маршрутизация действий (планируется)
├── lifecycle.py          # запуск / остановка / цикл (планируется)
├── self_monitor.py       # самонаблюдение (планируется)
├── improvement_planner.py # планирование улучшений (планируется)
└── feedback_requester.py  # обратная связь с пользователем (планируется)
```

### Модули

#### decision_engine.py

- **Роль**: Только координация - оркестрация работы других модулей
- **Функции**:
  - `run_once(goal: str) -> int` - сохраняет цель как задачу в БД и возвращает task_id (реализовано в MVP)
  - `run()` - главный цикл работы агента (планируется)
  - `handle_goal(goal)` - принимает новую цель/задачу и превращает её во внутренние действия (планируется)
  - `route(action)` - маршрутизирует действие в нужный модуль (память/LLM/код/тесты) (планируется)
  - `finalize(result)` - финализация: отчёт, запись опыта, обновление статусов (планируется)
- **Статус**: MVP: реализован `run_once()` — сохранение цели в БД через MemoryManager
- **Связи**: MemoryManager (используется), LLM Proxy (планируется), модули eva_code и eva_test (планируется)
- **Ограничение**: Не содержит логику обработки целей, маршрутизации или жизненного цикла (только сохранение цели на текущем этапе)

#### goal_handler.py

- **Роль**: Работа с целями и задачами
- **Функции**:
  - Получение и обработка входящих задач (внешних и внутренних)
  - Планирование решения (с участием LLM через ActionRouter)
  - Разбиение задачи на подзадачи
  - Оценка достижения цели
  - Формирование отчёта о результате
- **Связи**: ActionRouter (для планирования через LLM), MemoryManager (для контекста)

#### action_router.py

- **Роль**: Маршрутизация действий к модулям-исполнителям
- **Функции**:
  - Определение, какой модуль должен выполнить действие
  - Сопоставление типов действий с модулями (generate_code → CodeGenerator, run_tests → TestRunner)
  - Передача данных в нужный модуль
  - Обработка результатов от модулей
- **Связи**: Все модули eva_code, eva_test, eva_utils (LLM Proxy)

#### lifecycle.py

- **Роль**: Управление жизненным циклом системы
- **Функции**:
  - Запуск системы (инициализация модулей)
  - Остановка системы (корректное завершение)
  - Главный цикл работы агента
  - Управление очередью задач
  - Обработка ошибок на уровне системы
- **Связи**: DecisionEngine, GoalHandler, MemoryManager

#### memory_manager.py

- **Роль**: Центральное хранилище знаний Евы (долговременная память)
- **Функции**:
  - **Контекст для принятия решений**:
    - `get_context_for_goal(goal)` - возвращает контекст для обработки цели
    - `get_module_info(module_name)` - информация о модуле (версия, статус, метрики)
    - `get_recent_errors(module_name, limit)` - последние ошибки по модулю
  - **Запись результатов и опыта**:
    - `save_task(goal, status, source, meta)` - сохранение задачи
    - `save_plan(task_id, plan_text, meta)` - сохранение плана выполнения
    - `save_code_version(module_name, code_text, status, meta)` - сохранение версии кода
    - `save_test_result(task_id, status, output, code_version_id, meta)` - сохранение результатов тестов
    - `save_reflection(task_id, reflection, meta)` - сохранение рефлексии/уроков
    - `save_module(name, file_path, description, start_line, end_line, metrics, status, meta, content_hash)` - сохранение/обновление модуля в мета-карте (UPSERT по name, сохраняет content_hash для отслеживания изменений)
    - `update_module_last_seen(name)` - обновляет только last_seen_at для модуля (для оптимизации при неизменённых файлах)
  - **Чтение данных мета-карты**:
    - `get_module_by_name(name)` - возвращает модуль по name (включая content_hash) или None
  - **Работа с зависимостями (dependencies)**:
    - `save_dependency(from_module_name, to_module_name, kind)` - сохраняет связь между модулями (возвращает id зависимости, если связь уже существует - возвращает существующий id)
    - `delete_dependencies_for_module(module_name)` - удаляет все зависимости для модуля (и входящие, и исходящие), используется перед обновлением мета-карты модуля
    - `get_dependents(module_name, kind=None)` - возвращает список всех зависимостей модуля (входящих и исходящих), можно фильтровать по типу связи (kind: "import", "call", "other")
- **Статус**: Реализовано (MVP: основные методы для работы с БД, подключение к PostgreSQL, методы для работы с dependencies)
- **Связи**: DecisionEngine, SelfMonitor, ImprovementPlanner
- **Важно**: DecisionEngine не должен содержать SQL и детали БД - вся работа через MemoryManager

#### self_monitor.py

- **Роль**: Модуль самонаблюдения - даёт Еве самосознание
- **Функции**:
  - `scan()` - сканирует проект и строит мета-карту кода:
    - Находит все `.py` файлы рекурсивно (пропускает `.venv`, `venv`, `__pycache__`, `.git`, `site-packages`)
    - Вычисляет SHA256 hash каждого файла для отслеживания изменений
    - Сравнивает hash с сохранённым в БД:
      - Если hash совпадает → обновляет только `last_seen_at` (файл не изменился)
      - Если hash отличается или файл новый → обновляет/создаёт запись с новым `content_hash`
    - Помечает удалённые файлы (после сканирования: `last_seen_at = NULL` → `status = 'deleted'`)
  - `_compute_file_hash(file_path)` - вычисляет SHA256 hash содержимого файла
  - Парсинг AST (планируется) - извлечение функций, классов, импортов
  - Сбор статических метрик (планируется) - сложность, покрытие тестами, связи
- **Статус**: Реализовано (MVP: сканирование файлов и отслеживание изменений через hash)
- **Связи**: MemoryManager (сохранение модулей и мета-карты), DecisionEngine (планируется)

#### improvement_planner.py

- **Роль**: "Внутренний аналитик" - планирование самоулучшений
- **Функции**:
  - Анализ ошибок из ReflectionLog
  - Анализ динамики метрик кода
  - Формирование задач улучшения для DecisionEngine
  - Приоритизация улучшений
- **Связи**: SelfMonitor, MemoryManager, DecisionEngine

#### feedback_requester.py

- **Роль**: Модуль обратной связи с пользователем
- **Функции**:
  - Запрос помощи/подтверждения у пользователя
  - Логирование вопросов
  - Отправка уведомлений через интерфейс
- **Связи**: DecisionEngine, ImprovementPlanner

---

## eva_code/ - Генерация и редактирование кода

**Назначение**: Модули для создания и модификации кода ("руки" системы).

### Модули:

#### code_generator.py

- **Роль**: Генерация нового кода
- **Функции**:
  - `generate_code(spec)` - генерация кода по спецификации
  - Формирование промптов для LLM
  - Сохранение сгенерированного кода
  - Работа с extract_libraries для зависимостей
- **Связи**: LLM Proxy, DecisionEngine

#### code_editor.py

- **Роль**: Точечное редактирование существующего кода
- **Функции**:
  - `modify_function()` - замена тела функции
  - `add_method()` - добавление метода в класс
  - `insert_import()` - добавление импорта
  - `delete_lines()` - удаление строк
  - Парсинг и модификация через AST
- **Связи**: DecisionEngine, LLM Proxy (для сложных правок), SelfMonitor

#### code_checker.py

- **Роль**: Верификация и статическая проверка кода
- **Функции**:
  - Запуск линтера (flake8/pylint)
  - Проверка соответствия структуры
  - Валидация контрактов (входы/выходы)
  - Автоматическое формирование тестов-шаблонов
- **Связи**: DecisionEngine, CodeGenerator, CodeEditor

---

## eva_test/ - Тестирование и песочница

**Назначение**: Модули для безопасного тестирования кода ("лаборатория").

### Модули:

#### test_generator.py

- **Роль**: Генерация тестовых сценариев
- **Функции**:
  - `generate_tests(module_name, spec)` - создание тестов
  - Формирование запросов к LLM для генерации тестов
  - Использование шаблонов тестов
  - Сохранение тестов во временные файлы
- **Связи**: LLM Proxy, DecisionEngine

#### test_runner.py

- **Роль**: Запуск тестов в Docker-песочнице
- **Функции**:
  - `run_tests(target_module)` - изолированный запуск тестов
  - Использование SandboxManager для подготовки контейнера
  - Сбор результатов выполнения
  - Управление таймаутами и ресурсами
- **Связи**: SandboxManager, DecisionEngine

#### test_analyzer.py

- **Роль**: Анализ результатов тестирования
- **Функции**:
  - `analyze_results(test_log)` - парсинг логов тестов
  - Определение типов ошибок (ImportError, AssertionError, и т.д.)
  - Формирование рекомендаций по исправлению
  - Использование LLM для сложного анализа
- **Связи**: DecisionEngine, LLM Proxy, ImprovementPlanner

#### sandbox_manager.py

- **Роль**: Управление Docker-контейнерами
- **Функции**:
  - Создание/запуск/удаление контейнеров
  - Подготовка окружения (установка зависимостей)
  - Ограничение ресурсов (CPU/RAM)
  - Изоляция выполнения кода
- **Связи**: TestRunner

---

## eva_utils/ - Вспомогательные утилиты

**Назначение**: Общие утилиты для работы системы.

### Модули:

#### state_manager.py

- **Роль**: Управление состоянием системы
- **Функции**:
  - Флаги состояния модулей ("АКТУАЛЬНО" / "НА ИЗМЕНЕНИИ")
  - Отслеживание статусов выполнения
- **Связи**: DecisionEngine, SelfMonitor

#### code_map.py

- **Роль**: Логика сбора структуры кода (мета-карты)
- **Функции**:
  - Построение графа зависимостей
  - Определение связей между модулями
  - (Может быть частью self_monitor)
- **Связи**: SelfMonitor

#### extract_libraries.py

- **Роль**: Извлечение списка требуемых библиотек из кода
- **Функции**:
  - Анализ импортов в коде
  - Формирование списка зависимостей
- **Связи**: CodeGenerator, SandboxManager

#### install_libraries.py

- **Роль**: Установка библиотек
- **Функции**:
  - Установка пакетов через pip
  - Подготовка requirements.txt
- **Связи**: SandboxManager

#### cleanup_libraries.py

- **Роль**: Очистка зависимостей
- **Функции**:
  - Удаление неиспользуемых библиотек
  - Очистка временных установок
- **Связи**: SandboxManager

#### logger.py (предполагается)

- **Роль**: Логирование событий системы
- **Функции**: Централизованное логирование

#### config.py (предполагается)

- **Роль**: Управление конфигурацией
- **Функции**: Загрузка настроек, переменных окружения

---

## Файлы в корне проекта

### llm_proxy.py

- **Роль**: Единая точка доступа к языковым моделям (LLM)
- **Расположение**: Корень проекта (не в eva_utils/)
- **Функции**:
  - `choose_model(task_type)` - выбор модели по типу задачи:
    - `"chat"` → модель диалога/планирования (gpt-4o по умолчанию)
    - `"code"` → модель кода/тестов (gpt-5.2 по умолчанию)
  - `request(task_type, prompt)` - единая точка запроса к LLM
  - Загрузка конфигурации из .env:
    - `OPENAI_API_KEY` - ключ API
    - `OPENAI_CHAT_MODEL` - модель для диалога/планирования
    - `OPENAI_CODE_MODEL` - модель для генерации кода
- **Статус**: Каркас создан (заглушка без реальных сетевых вызовов)
- **Связи**: DecisionEngine, CodeGenerator, TestGenerator, TestAnalyzer
- **Правило архитектуры**: В других модулях НЕ должно быть прямых вызовов OpenAI SDK - только через LLMProxy
- **Классы**:
  - `LLMModels` (dataclass) - контейнер имён моделей (chat, code)

### main.py

- **Роль**: Точка входа в систему Евы 2.0
- **Расположение**: Корень проекта
- **Функции**:
  - `main() -> int` - главная функция:
    - Загружает переменные окружения из `.env` (через `python-dotenv`)
    - Проверяет наличие `POSTGRES_DSN` (выводит SET/NOT SET)
    - Создаёт `MemoryManager` (подключение к PostgreSQL)
    - Проверяет подключение к БД через `mm.ping()` (SELECT 1)
    - Тестирует интеграцию `DecisionEngine` + `MemoryManager` (создаёт тестовую задачу через `engine.run_once()`)
    - Закрывает соединение с БД
- **Статус**: Реализовано (MVP: минимальная проверка окружения и БД)
- **Связи**: MemoryManager, DecisionEngine
- **Возвращаемые коды**:
  - `0` - успех (БД доступна)
  - `1` - ошибка инициализации MemoryManager
  - `2` - ошибка ping к БД

---

## eva_api/ - Интерфейс

**Назначение**: Интерфейсы для взаимодействия с системой (опционально на MVP).

### Модули:

#### api.py

- **Роль**: FastAPI endpoints для веб-доступа
- **Функции**: REST API для управления задачами
- **Связи**: DecisionEngine

#### cli.py

- **Роль**: Интерфейс командной строки
- **Функции**: CLI для запуска задач, просмотра статуса
- **Связи**: DecisionEngine

---

## reflection_log/ - Журнал рефлексии

**Назначение**: Хранение журнала рефлексии и опыта системы.

### Файлы

#### reflection_log.yaml (или в БД)

- **Формат записей**:
  - Время события
  - Описание действия/этапа
  - Результат (успех/неуспех)
  - Причина неудачи (если есть)
  - Урок (если выучен)
- **Использование**: ImprovementPlanner анализирует для выявления паттернов

---

## Поток данных (основной цикл)

1. **Постановка задачи**: Пользователь → DecisionEngine
2. **Доступ к контексту**: DecisionEngine → MemoryManager → PostgreSQL
3. **Самоанализ**: DecisionEngine → SelfMonitor → обновление мета-карты
4. **Планирование**: DecisionEngine → LLM Proxy → GPT-4
5. **Генерация кода**: DecisionEngine → CodeGenerator → LLM Proxy
6. **Обновление мета-карты**: CodeGenerator → SelfMonitor → MemoryManager
7. **Генерация тестов**: DecisionEngine → TestGenerator → LLM Proxy
8. **Запуск тестов**: DecisionEngine → TestRunner → SandboxManager → Docker
9. **Анализ результатов**: TestRunner → TestAnalyzer → DecisionEngine
10. **Исправление (если нужно)**: DecisionEngine → CodeEditor → цикл повторяется
11. **Завершение**: DecisionEngine → ReflectionLog → MemoryManager
12. **Самоулучшение**: ImprovementPlanner → анализ ReflectionLog → новые цели → DecisionEngine

---

## База данных (PostgreSQL)

**Схемы**:

- `data/schema.sql` - источник истины для таблиц MemoryManager (задачи, планы, версии кода, тесты, рефлексия)
- `data/schema_code_map.sql` - мета-карта кода (модули и зависимости)

**Таблицы в БД (схема `public`):**

1. `code_versions`
2. `dependencies`
3. `modules`
4. `plans`
5. `reflections`
6. `tasks`
7. `test_results`

### Детальная структура таблиц

#### 1. tasks - входящие цели/задачи

**Колонки:**

- `id` (BIGINT, NOT NULL, PRIMARY KEY, DEFAULT: nextval('tasks_id_seq'))
- `goal` (TEXT, NOT NULL)
- `status` (TEXT, NOT NULL, DEFAULT: 'new')
- `source` (TEXT, NOT NULL, DEFAULT: 'user')
- `meta` (JSONB, NULL)
- `created_at` (TIMESTAMP WITHOUT TIME ZONE, NOT NULL, DEFAULT: CURRENT_TIMESTAMP)
- `updated_at` (TIMESTAMP WITHOUT TIME ZONE, NOT NULL, DEFAULT: CURRENT_TIMESTAMP)
- `priority` (INTEGER, NOT NULL, DEFAULT: 0)

**Индексы:**

- `tasks_pkey` (PRIMARY KEY на `id`)
- `idx_tasks_status` (`status`)
- `idx_tasks_created_at` (`created_at DESC`)
- `idx_tasks_priority` (`priority DESC`)
- `idx_tasks_status_created` (`status`, `created_at DESC`)

**Статусы:** `new`, `in_progress`, `done`, `failed`  
**Источники:** `user`, `improvement_planner`, `internal`

#### 2. plans - планы по задачам

**Колонки:**

- `id` (BIGINT, NOT NULL, PRIMARY KEY, DEFAULT: nextval('plans_id_seq'))
- `task_id` (BIGINT, NOT NULL, FOREIGN KEY → tasks.id ON DELETE CASCADE)
- `plan_text` (TEXT, NOT NULL)
- `meta` (JSONB, NULL)
- `created_at` (TIMESTAMP WITHOUT TIME ZONE, NOT NULL, DEFAULT: CURRENT_TIMESTAMP)

**Foreign Keys:**

- `plans_task_id_fkey`: `task_id` → `tasks.id` (ON DELETE CASCADE)

**Индексы:**

- `plans_pkey` (PRIMARY KEY на `id`)
- `idx_plans_task_id` (`task_id`)
- `idx_plans_created_at` (`created_at DESC`)
- `idx_plans_task_created` (`task_id`, `created_at DESC`)

#### 3. code_versions - версии кода (по модулям)

**Колонки:**

- `id` (BIGINT, NOT NULL, PRIMARY KEY, DEFAULT: nextval('code_versions_id_seq'))
- `module_name` (TEXT, NOT NULL)
- `status` (TEXT, NOT NULL, DEFAULT: 'draft')
- `code_text` (TEXT, NOT NULL)
- `meta` (JSONB, NULL)
- `created_at` (TIMESTAMP WITHOUT TIME ZONE, NOT NULL, DEFAULT: CURRENT_TIMESTAMP)

**Индексы:**

- `code_versions_pkey` (PRIMARY KEY на `id`)
- `idx_code_versions_module_name` (`module_name`)
- `idx_code_versions_created_at` (`created_at DESC`)
- `idx_code_versions_module_created` (`module_name`, `created_at DESC`)

**Статусы:** `draft`, `active`, `deprecated`, и т.д.

#### 4. test_results - результаты тестов

**Колонки:**

- `id` (BIGINT, NOT NULL, PRIMARY KEY, DEFAULT: nextval('test_results_id_seq'))
- `task_id` (BIGINT, NOT NULL, FOREIGN KEY → tasks.id ON DELETE CASCADE)
- `code_version_id` (BIGINT, NULL, FOREIGN KEY → code_versions.id ON DELETE SET NULL)
- `status` (TEXT, NOT NULL)
- `output` (TEXT, NULL)
- `meta` (JSONB, NULL)
- `created_at` (TIMESTAMP WITHOUT TIME ZONE, NOT NULL, DEFAULT: CURRENT_TIMESTAMP)

**Foreign Keys:**

- `test_results_task_id_fkey`: `task_id` → `tasks.id` (ON DELETE CASCADE)
- `test_results_code_version_id_fkey`: `code_version_id` → `code_versions.id` (ON DELETE SET NULL)

**Индексы:**

- `test_results_pkey` (PRIMARY KEY на `id`)
- `idx_test_results_task_id` (`task_id`)
- `idx_test_results_code_version` (`code_version_id`)
- `idx_test_results_status` (`status`)
- `idx_test_results_created_at` (`created_at DESC`)
- `idx_test_results_task_created` (`task_id`, `created_at DESC`)

**Статусы:** `pass`, `fail`, `error`

#### 5. reflections - рефлексия/уроки по задаче

**Колонки:**

- `id` (BIGINT, NOT NULL, PRIMARY KEY, DEFAULT: nextval('reflections_id_seq'))
- `task_id` (BIGINT, NOT NULL, FOREIGN KEY → tasks.id ON DELETE CASCADE)
- `reflection` (TEXT, NOT NULL)
- `meta` (JSONB, NULL)
- `created_at` (TIMESTAMP WITHOUT TIME ZONE, NOT NULL, DEFAULT: CURRENT_TIMESTAMP)

**Foreign Keys:**

- `reflections_task_id_fkey`: `task_id` → `tasks.id` (ON DELETE CASCADE)

**Индексы:**

- `reflections_pkey` (PRIMARY KEY на `id`)
- `idx_reflections_task_id` (`task_id`)
- `idx_reflections_created_at` (`created_at DESC`)
- `idx_reflections_task_created` (`task_id`, `created_at DESC`)

#### 6. modules - мета-карта модулей

**Колонки:**

- `id` (BIGINT, NOT NULL, PRIMARY KEY, DEFAULT: nextval('modules_id_seq'))
- `name` (TEXT, NOT NULL, UNIQUE)
- `description` (TEXT, NULL)
- `file_path` (TEXT, NOT NULL)
- `start_line` (INTEGER, NULL)
- `end_line` (INTEGER, NULL)
- `metrics` (JSONB, NULL)
- `status` (TEXT, NOT NULL, DEFAULT: 'unknown')
- `created_at` (TIMESTAMP WITH TIME ZONE, NOT NULL, DEFAULT: CURRENT_TIMESTAMP)
- `updated_at` (TIMESTAMP WITH TIME ZONE, NOT NULL, DEFAULT: CURRENT_TIMESTAMP)
- `last_seen_at` (TIMESTAMP WITH TIME ZONE, NULL)
- `content_hash` (TEXT, NULL)
- `meta` (JSONB, NULL)

**Назначение полей:**

- `content_hash` - SHA256 hash содержимого файла для отслеживания изменений
- `last_seen_at` - время последнего обнаружения файла при сканировании (NULL = файл не найден/удалён)

**Индексы:**

- `modules_pkey` (PRIMARY KEY на `id`)
- `modules_name_key` (UNIQUE на `name`)

**Использование:** SelfMonitor сохраняет информацию о структуре кода и отслеживает изменения через hash.

#### 7. dependencies - связи между модулями

**Колонки:**

- `id` (BIGINT, NOT NULL, PRIMARY KEY, DEFAULT: nextval('dependencies_id_seq'))
- `from_module_id` (BIGINT, NOT NULL, FOREIGN KEY → modules.id ON DELETE CASCADE)
- `to_module_id` (BIGINT, NOT NULL, FOREIGN KEY → modules.id ON DELETE CASCADE)
- `kind` (TEXT, NOT NULL, DEFAULT: 'call')
- `created_at` (TIMESTAMP WITH TIME ZONE, NOT NULL, DEFAULT: CURRENT_TIMESTAMP)

**Индексы:**

- `dependencies_pkey` (PRIMARY KEY на `id`)
- `dependencies_from_module_id_to_module_id_kind_key` (UNIQUE на `from_module_id`, `to_module_id`, `kind`)

**Foreign Keys:**

- `dependencies_from_module_id_fkey`: `from_module_id` → `modules.id` (ON DELETE CASCADE)
- `dependencies_to_module_id_fkey`: `to_module_id` → `modules.id` (ON DELETE CASCADE)

**Ограничения:**

- UNIQUE (from_module_id, to_module_id, kind)

**Типы связей:** `call`, `import`, `other`

---

## Внешние зависимости

- **Python 3.x** - основной язык
- **PostgreSQL** - база данных памяти
- **Docker** - песочница для тестирования
- **GPT-4 API** (или другая LLM) - генерация кода и планов
- **Библиотеки**:
  - OpenAI SDK (или аналог)
  - psycopg2 / SQLAlchemy (PostgreSQL)
  - docker Python SDK
  - ast (парсинг кода)
  - radon (метрики кода)
  - flake8/pylint (проверка кода)
  - pytest/unittest (тестирование)

---

## Метрики успеха

- **Автономность**: процент задач, решённых без помощи
- **Качество кода**: метрики сложности, покрытие тестами
- **Обучаемость**: уменьшение числа итераций для схожих задач
- **Стабильность**: отсутствие регрессий после улучшений
- **Быстродействие**: время выполнения задач, время доступа к памяти

---

## Примечания

- На этапе MVP многие модули могут иметь упрощённую реализацию
- Структура рассчитана на масштабирование
- Каждый модуль должен иметь чёткий интерфейс ввода/вывода
- Связи между модулями могут быть явными (в коде) или храниться в БД (на будущее)
