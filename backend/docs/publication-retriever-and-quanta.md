# Ретривер публикаций и вывод квантов на фронт

Краткое описание цепочки: ретривер публикаций (OpenAlex) → обработка квантов → сохранение → отображение на фронте.

---

## 1. Ретривер публикаций

**Назначение:** поиск публикаций по теме и формирование квантов (атомарных единиц информации).

**Компоненты:**

- **SearchPlanner** (`app/integrations/search/plan.py`) — строит план из `theme_search_queries`: для каждой включённой записи и каждого языка темы создаётся шаг с `QueryStep` (query_model, retriever, max_results). Лимит на шаг берётся из `SEARCH_MAX_RESULTS_PER_RETRIEVER` (OpenAlex: 50).
- **PublicationRetriever** (`app/integrations/search/retrievers/publication/retriever.py`) — оркестратор: получает `QueryStep` и `RetrieverContext`, вызывает **OpenAlexPublicationAdapter**. В контексте обязательны `theme_id`, `terms_by_id`, язык шага или темы.
- **OpenAlexPublicationAdapter** (`.../openalex/adapter.py`) — компилирует `QueryModel` в boolean-запрос OpenAlex (keywords, MUST, EXCLUDE), запрашивает API, маппит ответ в `QuantumCreate`, отдаёт только публикации с абстрактом (`require_abstract=True`).

**Источник запросов:** таблица `theme_search_queries` (поля `query_model`, `order_index`, `enabled_retrievers`). Языки плана — из `theme.languages`.

---

## 2. Порядок обработки полученных квантов

1. **Поиск по теме**  
   `POST /api/v1/search/collect-by-theme` → `SearchService.collect_links_for_theme()`:
   - загрузка темы и `theme_search_queries`;
   - построение плана (Planner);
   - **Executor** по шагам плана вызывает ретривер (OpenAlex), для каждого шага:
     - применяет **TimeSlice** по `date_at` (если передан);
     - **дедуп** по `(theme_id, dedup_key)`;
     - добавляет кванты в общий список до достижения `global_target_links`;
   - общий **дедуп** по списку, обрезка до `global_target_links`;
   - возврат `QuantumCollectResult` (items, plan, step_results).

2. **Перевод полей на основной язык темы**  
   Для квантов, у которых язык контента не совпадает с основным языком темы (`theme.languages[0]`), переводятся поля `title`, `summary_text`, `key_points`. Метод перевода задаётся в конфиге (`QUANTA_TRANSLATION_METHOD`):
   - **`translator`** (по умолчанию) — интеграция перевода в `app/integrations/translation`: верхний слой **TranslationService** вызывает выбранный переводчик (имя в `TRANSLATOR`: `deepl`, `yandex_translator`, …). Исходный язык берётся из кванта (`q.language`), целевой — основной язык темы; оба передаются в переводчик явно. Результат перевода включает оценку стоимости (пока — число входящих символов `input_characters`). Переводчики: **DeepL** — REST API, ключ `DEEPL_API_KEY`; **Yandex** (`yandex_translator`) — Yandex Cloud Translate REST (`https://translate.api.cloud.yandex.net`), ключ `YANDEX_API_KEY_TRANSLATE`, каталог `YANDEX_FOLDER_ID` (тот же, что для поиска).
   - **`llm`** — прежний способ: батчи по 5 квантов, вызов LLM (промпт `quanta.translate_fields.v1`), парсинг JSON из ответа, словарь «индекс → переводы».

3. **Сохранение в БД**  
   `save_quanta_from_search()`:
   - для каждого кванта из результата поиска — upsert в `theme_quanta` по `(theme_id, dedup_key)`;
   - при наличии перевода для индекса — запись полей `title_translated`, `summary_text_translated`, `key_points_translated` (при конфликте перезаписываются из входящей строки, если не NULL).

4. **Ответ API**  
   `collect-by-theme` возвращает тот же `QuantumCollectResult` (items, total_found, total_returned); кванты уже сохранены в БД с переводами.

---

## 3. Вывод квантов на фронт

1. **Запуск поиска**  
   Пользователь на странице темы нажимает «Поиск информации» → вызывается `runSearchByTheme({ theme_id, target_links: 50 })` → `POST /api/v1/search/collect-by-theme`. После ответа переключается активная вкладка на «Кванты» и вызывается `loadQuanta()`.

2. **Загрузка списка**  
   `loadQuanta()` → `GET /api/v1/themes/:themeId/quanta?limit=200` → `listThemeQuanta()`. Ответ: `{ items: QuantumOutDto[], total }`. Данные кладутся в стор темы: `data.quanta.items`, `data.quanta.total`.

3. **Отображение**  
   Вкладка «Кванты» рендерит `QuantaList` с `items` из стора. Для каждого кванта:
   - **Заголовок:** `title_translated ?? title`;
   - **Описание:** `summary_text_translated ?? summary_text`;
   - **Ключевые пункты:** `key_points_translated ?? key_points`.  
   Если переведённое поле `null`, показывается оригинал.

**Маршрут:** `/topic/quanta` → компонент страницы с `QuantaTab`, внутри — список квантов и при необходимости кнопка запуска поиска.

---

## Схема потоков

```
theme_search_queries → Planner → [QueryStep × языки]
       → Executor → PublicationRetriever → OpenAlex API
       → дедуп, time_slice, обрезка по target_links
       → QuantumCollectResult.items

items → по QUANTA_TRANSLATION_METHOD:
     translator → TranslationService → translators/<TRANSLATOR> (deepl | yandex_translator, source_lang + target_lang)
     llm       → translate_quanta_create_items (батчи по 5, LLM)
     → translations_by_index (+ при translator: input_characters в лог)

items + translations_by_index → save_quanta_from_search
     → theme_quanta (upsert по theme_id, dedup_key)

Фронт: runSearchByTheme → loadQuanta → GET .../quanta
     → QuantaList: title_translated ?? title, summary_text_translated ?? summary_text, key_points_translated ?? key_points
```
