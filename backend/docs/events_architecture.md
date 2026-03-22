## Архитектура событий (Event = hyperedge)

Этот документ описывает текущую реализацию событий в системе аналитики: модели, таблицы БД и основные принципы работы.

### Общая идея

- **Event = hyperedge**: событие — это контейнер, который связывает:
  - тему (`themes`),
  - сюжет (`event_plots`),
  - участников с ролями (`event_participants`),
  - атрибуты события (`event_attributes`).
- Сами события живут в таблице `events`; все дополнительные аспекты (роли, участники, сюжеты, атрибуты) вынесены в отдельные таблицы.
- Связь с доказательствами (квантами, источниками и т.п.) будет развиваться через другие модули (`quanta`, `relation` и др.).

---

## Таблица `events`

**Назначение**: базовый контейнер события внутри темы.

Ключевые поля:
- `id` — UUID PK, идентификатор события.
- `theme_id` — FK на `themes.id`; событие всегда принадлежит одной теме.
- `run_id` — UUID, ссылка на запуск пайплайна (без FK, только индекс).
- Временные поля:
  - `occurred_at` — точное/примерное время события.
  - `occurred_start`, `occurred_end` — интервал, если событие протяжённое.
  - `time_precision` — точность времени (`exact|day|month|year|unknown`).
- Описание:
  - `title` — короткое название.
  - `summary` — расширенное текстовое описание.
- Качество:
  - `confidence` — уверенность извлечения (0..1).
  - `importance` — важность для пользователя (0..1).
- Поля сюжета:
  - `plot_id` — FK на `event_plots.id` (ON DELETE SET NULL).
  - `plot_status` — статус привязки к сюжету (`unassigned/assigned/needs_review/proposed`).
  - `plot_confidence` — уверенность классификации по сюжету.
  - `plot_proposed_payload` — JSONB с предложением нового сюжета от LLM.
- Жизненный цикл:
  - `created_at`, `updated_at` — аудиторные поля.
  - `deleted_at` — soft delete.
- Служебное:
  - `extraction_version` — версия промпта/логики извлечения.

Основные индексы:
- `idx_events_theme_created_at (theme_id, created_at DESC)` — лента событий по теме.
- `idx_events_theme_occurred_at (theme_id, occurred_at DESC)` — хронология событий.
- `idx_events_plot_status (theme_id, plot_status, created_at DESC)` — отбор событий по статусу сюжета.
- `idx_events_run_id (run_id)` — поиск по запуску пайплайна.
- `idx_events_plot_proposed_payload_gin (plot_proposed_payload gin)` — фильтры/поиск по JSON предложенного сюжета.

---

## Таблица `event_roles`

**Назначение**: глобальный словарь ролей участников событий (универсальная «грамматика»).

- `id` — UUID PK.
- `code` — **уникальный** машинный код роли (например, `actor`, `target`, `cause`, `effect`, `instrument`, `location` и т.п.).
- `title` — человекочитаемое имя роли.
- `description` — пояснение, когда и как использовать роль.
- `created_at`, `updated_at` — аудиторные поля.

Используется в `event_participants.role_id`.

---

## Таблица `event_participants`

**Назначение**: участники события (сущность + роль) — реализация hyperedge.

- `id` — UUID PK.
- `event_id` — FK на `events.id` (ON DELETE CASCADE).
- `entity_id` — FK на `entities.id` (ON DELETE SET NULL); может быть `NULL`, если участник ещё не нормализован.
- `role_id` — FK на `event_roles.id`.
- `confidence` — уверенность извлечения связи (0..1).
- `added_at` — время добавления участника.

Ограничения и индексы:
- `UNIQUE(event_id, role_id, entity_id)` — не допускает дубликатов одной и той же сущности в одной роли в рамках события.
- `idx_event_participants_event (event_id)` — быстрый доступ к участникам события.
- `idx_event_participants_entity_id (entity_id)` — все события для сущности.
- `idx_event_participants_role (role_id)` — все участники с конкретной ролью.
- `idx_event_participants_entity_role (entity_id, role_id)` — связи «сущность + роль».
- `idx_event_participants_event_role (event_id, role_id)` — фильтрация участников события по роли.

Связи в ORM:
- `Event.participants` ↔ `EventParticipant.event`
- `EventRole.participants` ↔ `EventParticipant.role`

---

## Таблица `event_plots`

**Назначение**: «сюжеты» событий в рамках темы (theme-scoped). Пользователь может просматривать, одобрять и редактировать сюжеты.

Поля:
- `id` — UUID PK.
- `theme_id` — FK на `themes.id` (ON DELETE CASCADE).
- `code` — код сюжета; **уникален в рамках темы** (`UNIQUE(theme_id, code)`).
- `title` — название сюжета.
- `description` — описание/объяснение сюжета.
- `status` — статус сюжета (`draft/approved/archived`).
- `required_roles` — JSONB-массив кодов ролей, которые должны присутствовать (по `event_roles.code`).
- `optional_roles` — JSONB-массив опциональных ролей.
- `required_attributes` — JSONB-массив кодов атрибутов, которые должны быть заданы (по `event_attribute_defs.code`).
- `allowed_attributes` — JSONB-массив разрешённых атрибутов.
- `aliases` — JSONB со синонимами/вариантами названия.
- `created_by_user_id` — FK на `users.id`, кто создал (ON DELETE SET NULL).
- `approved_by_user_id` — FK на `users.id`, кто одобрил (ON DELETE SET NULL).
- `approved_at` — время одобрения.
- `created_at`, `updated_at` — аудиторные поля.

Индексы:
- `idx_event_plots_theme_status (theme_id, status, code)` — выборка сюжетов по теме и статусу.
- `idx_event_plots_theme_updated (theme_id, updated_at DESC)` — последние изменённые сюжеты по теме.
- `gin_event_plots_required_roles (required_roles gin)` — поиск по обязательным ролям.
- `gin_event_plots_allowed_attributes (allowed_attributes gin)` — поиск по разрешённым атрибутам.

Связи в ORM:
- `Event.plot` ↔ `EventPlot.events`.

Embeddings:
- для `event_plots` используется тип `embedding_object_type = 'event_plot'` в таблице `embeddings` (для поиска по сюжетам).

---

## Таблица `event_attribute_defs`

**Назначение**: словарь характеристик событий (канонизация ключей), привязанный к теме.

Поля:
- `id` — UUID PK.
- `theme_id` — FK на `themes.id` (ON DELETE CASCADE).
- `code` — канонический код атрибута (например, `price`, `currency`, `stake_percent`, `value_before`, `value_after`, `delta_percent`).
- `title` — человекочитаемое имя атрибута.
- `description` — пояснение.
- `value_type` — тип значения (`number/text/bool/date/json`).
- `unit_kind` — тип единицы измерения (`none/currency/percent/time/length/mass/temperature/etc.`).
- `created_at`, `updated_at` — аудиторные поля.

Ограничения/индексы:
- `UNIQUE(theme_id, code)` — один код атрибута внутри темы.
- `idx_event_attr_defs_theme (theme_id, code)` — быстрый поиск определения по коду в теме.

Связи:
- `EventAttributeDef.attribute_values` ↔ `EventAttribute.def_`.

---

## Таблица `event_attributes`

**Назначение**: конкретные значения характеристик для события.

Поля:
- `id` — UUID PK.
- `event_id` — FK на `events.id` (ON DELETE CASCADE).
- `attribute_def_id` — FK на `event_attribute_defs.id` (ON DELETE RESTRICT).
- `value_num` — числовое значение (NUMERIC).
- `value_text` — текстовое значение.
- `value_bool` — булево значение.
- `value_ts` — значение типа «дата/время».
- `value_json` — произвольное JSON-значение (по умолчанию `{}`).
- `unit` — конкретная единица измерения (например, `USD`, `days`).
- `currency` — валюта (если применимо).
- `confidence` — уверенность извлечения значения (0..1).
- `added_at` — время добавления.

Ограничения:
- CHECK `ck_event_attributes_at_least_one_value`:
  - запрещает строку, где **все** `value_num`, `value_text`, `value_bool`, `value_ts` равны `NULL` **и** `value_json` пустой (`NULL` или `{}`).
  - таким образом, атрибут всегда содержит хотя бы одно реальное значение.
- UNIQUE(event_id, attribute_def_id) — в текущей версии по одному значению атрибута данного типа на событие (упрощает обновление).

Индексы:
- `idx_event_attributes_event (event_id)` — все атрибуты события.
- `idx_event_attributes_def (attribute_def_id)` — поиск всех значений данного атрибута.
- `idx_event_attributes_def_num (attribute_def_id, value_num)` — числовая аналитика (поиск/сортировка).
- `idx_event_attributes_def_ts (attribute_def_id, value_ts)` — временные ряды по атрибутам.
- `gin_event_attributes_value_json (value_json gin)` — поиск по сложным JSON-структурам.

Связи:
- `Event.attributes` ↔ `EventAttribute.event`.
- `EventAttribute.def_` ↔ `EventAttributeDef.attribute_values`.

---

## Связь с другими модулями

- **Темы (`themes`)**:
  - `events.theme_id`, `event_plots.theme_id`, `event_attribute_defs.theme_id` — все события, сюжеты и определения атрибутов жёстко привязаны к теме.
- **Пользователи (`users`)**:
  - `event_plots.created_by_user_id`, `event_plots.approved_by_user_id` — кто создал и кто утвердил сюжет.
- **Сущности (`entities`)**:
  - `event_participants.entity_id` — нормализованные участники (организации, персоны и т.п.).
- **Embeddings (`embeddings`)**:
  - используется тип `object_type = 'event_plot'` для векторных представлений сюжетов.

---

## Резюме

Архитектура `Event = hyperedge` разносит разные аспекты событий по отдельным таблицам:

- `events` — **контейнер** события.
- `event_roles` — **словарь ролей**.
- `event_participants` — **гиперрёбра** «событие–сущность–роль».
- `event_plots` — **сюжеты** внутри темы, к которым могут быть привязаны события и embeddings.
- `event_attribute_defs` — **словарь атрибутов** внутри темы.
- `event_attributes` — **конкретные значения** атрибутов для событий.

Эта структура даёт гибкость (расширяемый словарь ролей и атрибутов, сюжеты поверх событий) и остаётся нормально индексируемой для аналитики и продуктовых фич.

