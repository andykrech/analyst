# Анализ: модель запросов на фронте и в бэкенде

## 1. Текущая структура данных

### Фронт (queryBuilder.ts, topicStore)

- **SavedQuery** — запрос хранит **только id терминов**:
  - `keywords.groups[].termIds: string[]`, `keywords.connectors`
  - `must.termIds: string[]`, `must.mode: 'ALL'|'ANY'`
  - `exclude.termIds: string[]`
- **Пулы** (keywordTerms, mustTerms, excludeTerms) — общие списки объектов `Term` (id, text, context, translations). Текст запроса собирается по termId из пулов.

### Бэкенд: таблица theme_search_queries (model.py + миграции)

После миграции `fa1b2c3d4e5`:

- Есть один столбец **`query_model`** (JSONB) — «структурная модель запроса».
- Удалены legacy-поля: `query_text`, `must_have`, `exclude`.
- Остальные поля: id, theme_id, order_index, title, time_window_days, target_links, enabled_retrievers, is_enabled.

**Вывод: схему таблицы менять не нужно** — один JSONB под произвольную структуру уже есть.

### Бэкенд: слой поиска (schemas.py, plan.py, exec.py, yandex_retriever.py)

Ожидаемая структура **QueryModel** (Pydantic):

- **keywords**: `KeywordsBlock` — `groups: list[KeywordGroup]`, `connectors: list["OR"|"AND"]`.
  - `KeywordGroup`: `op: "OR"|"AND"`, **`terms: list[str]`** (нормализованные **тексты** термов).
- **must**: `MustBlock` — `mode: "ALL"|"ANY"`, **`terms: list[str]`**.
- **exclude**: `ExcludeBlock` — **`terms: list[str]`**.

То есть бэкенд везде опирается на **термы как строки (текст)**, а не на id:

- В **plan.py**: `QueryModel.model_validate(row.query_model)` — из БД читается JSON и валидируется как QueryModel.
- В **exec.py**: фильтрация по `step.query_model.must.terms`, `step.query_model.exclude.terms` (списки строк).
- В **yandex_retriever.py**: `_compile_query_model_to_string(model)` собирает строку запроса из `group.terms`, `model.must.terms`, `model.exclude.terms` (всё list[str]).

**Вывод: менять схему таблицы или модель SQLAlchemy не нужно.** Нужно обеспечить, чтобы **в query_model в БД попадала структура с `terms: list[str]`**, а не `termIds`.

---

## 2. Расхождение фронт ↔ бэкенд

| Аспект              | Фронт                    | Бэкенд (QueryModel)     |
|---------------------|--------------------------|--------------------------|
| Ключевые в группе   | `termIds: string[]`      | `terms: list[str]`       |
| Обязательные        | `termIds: string[]`      | `terms: list[str]`       |
| Минус-слова         | `termIds: string[]`      | `terms: list[str]`       |
| Группы ключевых     | `groups[].id`, `termIds` | `groups[].terms` (без id)|

На бэкенде нет понятия «пулов» и «id терминов» — только готовые строки в запросе.

---

## 3. Нужно ли менять таблицу БД и слой поиска?

### Таблица БД (theme_search_queries)

- **Не менять.** Столбец `query_model` JSONB уже подходит. Важно лишь **формат JSON**, который в него пишется: он должен совпадать с бэкенд-схемой QueryModel (keywords.groups[].terms, must.terms, exclude.terms — списки строк).

### Модель Theme (themes)

- Сейчас: `keywords`, `must_have`, `exclude` — плоские JSONB (списки; по смыслу «подсказки для пользователя»). Поиск их не использует — источник истины для поиска только theme_search_queries.
- Для синхронизации с фронтом при сохранении/загрузке темы можно позже расширить формат (например, хранить термины с id и контекстом), но для **логики поиска** это не обязательно.

### Слой поиска (plan, exec, service, retrievers)

- **Не менять.** Вся логика завязана на QueryModel с **terms: list[str]**. Достаточно того, чтобы при сохранении в БД в `query_model` попадала именно такая структура.

---

## 4. Где и что нужно менять

### 4.1. Контракт при сохранении/загрузке темы (когда появится API)

Сейчас в theme router нет CRUD темы и запросов (есть только `/prepare` и `/terms/translate`). Когда будет API сохранения/загрузки темы:

- **При сохранении запросов (theme_search_queries):**
  - Фронт должен отдавать для каждого запроса не SavedQuery (с termIds), а **уже приведённую к QueryModel форму** с текстами:
    - по пулам разрешить каждый termId → `term.text` (с учётом текущего языка/переводов при необходимости);
    - сформировать объект: `{ keywords: { groups: [{ op, terms: string[] }], connectors }, must: { mode, terms: string[] }, exclude: { terms: string[] } }`.
  - Либо этот маппинг делается на бэкенде: тогда API принимает SavedQuery + пулы (keywordTerms, mustTerms, excludeTerms), а бэкенд по id подставляет text и пишет в query_model готовый QueryModel. Тогда фронт может слать «как есть», но бэкенду нужна новая схема приёма и слой преобразования termIds → terms.

- **При загрузке темы:**
  - Бэкенд отдаёт theme (keywords, must_have, exclude — как сейчас или в расширенном формате) и список theme_search_queries с query_model (уже с terms: list[str]).
  - Фронт должен восстановить пулы из theme и по возможности «наложить» сохранённые запросы на пулы (сопоставление по тексту или по будущему id в theme), чтобы показать конструктор и сохранённые слоты. Если в theme термины без id — фронт при загрузке генерирует id и при сохранении снова отдаёт query_model с текстами.

### 4.2. Рекомендация без смены бэкенд-контракта

- **Таблицу и слой поиска не трогать.**
- При появлении API сохранения темы/запросов:
  - **Вариант A (проще):** фронт при сохранении сам строит из SavedQuery + пулов объект в формате QueryModel (terms = тексты из пулов по termIds) и отправляет его в API; в БД в query_model пишется этот же объект. Загрузка: бэкенд отдаёт query_model с текстами; фронт из theme строит пулы, из query_model может строить превью/слоты (по тексту или создавая «виртуальные» термины для отображения).
  - **Вариант B:** API принимает termIds + отдельно пулы; бэкенд резолвит id → text и валидирует/пишет QueryModel. Тогда на бэкенде добавляется слой преобразования (SavedQuery-like → QueryModel) и, при необходимости, расширенные схемы приёма; таблица и план/исполнение поиска по-прежнему не меняются.

### 4.3. Соответствие структур (для варианта A)

Преобразование на фронте при сохранении (псевдологика):

- `keywords.groups` → для каждой группы: `termIds` → по пулу keywordTerms взять `term.text` → `terms: string[]`; `op` без изменений; `id` группы на бэкенд не нужен.
- `keywords.connectors` → без изменений.
- `must.termIds` → по пулу mustTerms взять тексты → `must.terms: string[]`; `mode` без изменений.
- `exclude.termIds` → по пулу excludeTerms взять тексты → `exclude.terms: string[]`.

Валидация на бэкенде уже есть: `QueryModel.model_validate(row.query_model)` — если прилетает такой JSON, план и исполнитель работают как сейчас.

---

## 5. Краткий итог

| Объект | Менять? | Причина |
|--------|--------|--------|
| Таблица theme_search_queries | **Нет** | query_model JSONB уже подходит; важен только формат JSON (terms = строки). |
| Модель ThemeSearchQuery (SQLAlchemy) | **Нет** | Тип query_model: dict/JSONB — достаточен. |
| Модель Theme (keywords, must_have, exclude) | **По желанию** | Для поиска не используется; расширение формата — только для удобства синхронизации с фронтом. |
| Search-схемы (QueryModel, KeywordGroup, MustBlock, ExcludeBlock) | **Нет** | Уже соответствуют «запрос с текстами». |
| Plan / Exec / Service / Retriever | **Нет** | Работают с QueryModel с terms: list[str]. |
| API сохранения/загрузки темы и запросов | **Да, при появлении** | Нужно договориться: либо фронт отдаёт query_model с текстами (вариант A), либо бэкенд принимает termIds + пулы и сам резолвит (вариант B). В обоих случаях слой поиска и таблица остаются без изменений. |

Итого: **модель таблицы и логику слоя поиска менять не нужно.** Нужно обеспечить, чтобы в `query_model` в БД сохранялась структура с **terms как списками строк** (как в текущем QueryModel бэкенда). Это достигается на этапе интеграции фронта с API (при сохранении темы/запросов) — либо преобразованием на фронте, либо приёмом termIds и резолвом на бэкенде.

---

## 6. Вариант: писать в БД «как на фронте», подставлять слова в начале слоя поиска

**Идея:** в `query_model` в БД хранить тот же формат, что и на фронте (termIds), а подстановку текстов делать один раз в самом начале слоя поиска — при построении плана. Остальная цепочка (Executor, Retriever) по-прежнему получает уже готовый QueryModel с `terms: list[str]`.

### Что это даёт

- Фронт при сохранении темы/запросов может слать **SavedQuery как есть** (termIds), без преобразования в тексты.
- Один формат запроса на фронте и в БД — меньше расхождений и дублирования логики резолва.
- Вся логика «id → текст» сосредоточена на бэкенде в одном месте (вход в слой поиска).

### Что нужно изменить

1. **Формат `query_model` в БД**  
   Хранить структуру «как на фронте»:
   - `keywords.groups[].termIds: string[]`, `keywords.connectors`;
   - `must.mode`, `must.termIds: string[]`;
   - `exclude.termIds: string[]`.  
   На бэкенде завести отдельную Pydantic-схему под этот формат (например `SavedQuerySchema` / «raw query model») для валидации при записи. Не валидировать его как текущий `QueryModel` при чтении для поиска — сначала резолвить.

2. **Таблица themes: пулы с id**  
   Чтобы по id подставить текст, нужны «пулы» с идентификаторами. Поля `theme.keywords`, `theme.must_have`, `theme.exclude` должны хранить списки объектов вида **`{ "id": "...", "text": "...", "context": "..." }`** (или как минимум `id` и `text`). Тогда при построении плана можно один раз по теме собрать словари id → text и по ним разрешить все termIds из запросов.

3. **Вход в слой поиска — SearchPlanner.build_plan_for_theme**  
   В самом начале:
   - загрузить не только строки `theme_search_queries`, но и **тему** (Theme) по `theme_id`;
   - по полям темы `keywords`, `must_have`, `exclude` построить три маппинга: `keyword_id → text`, `must_id → text`, `exclude_id → text` (при отсутствии id можно падать в ошибку или пропускать терм — политика на выбор);
   - для каждой строки `row` из `theme_search_queries`: взять `row.query_model` (форма с termIds), по маппингам заменить каждый termId на текст, собрать объект в формате текущего **QueryModel** (groups[].terms, must.terms, exclude.terms — списки строк);
   - вызвать `QueryModel.model_validate(resolved_dict)` и передать уже **resolved** QueryModel в `QueryStep(..., query_model=...)`.

Дальше **Executor, Retriever, схемы QueryModel/KeywordGroup/MustBlock/ExcludeBlock не трогать** — они по-прежнему работают только с `terms: list[str]`.

### Итог по варианту

| Что | Действие |
|-----|----------|
| Таблица theme_search_queries | Оставить как есть; в `query_model` хранить формат с **termIds** (как на фронте). |
| Таблица themes | Договориться о формате: в `keywords`, `must_have`, `exclude` хранить объекты с полями **id** и **text** (и при необходимости context), чтобы по ним можно было резолвить. |
| SearchPlanner.build_plan_for_theme | Дополнить: загрузка темы, построение id→text из полей темы, преобразование каждого `row.query_model` (termIds) в QueryModel (terms) и передача в QueryStep. |
| Остальной слой поиска (exec, service, retriever, QueryModel-схемы) | Не менять — они получают уже «разрешённый» QueryModel с текстами. |

Так можно и сохранять в БД в формате фронта, и подставлять слова в самом начале слоя поиска.
