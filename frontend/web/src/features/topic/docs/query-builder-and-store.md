# Конструктор запросов и стор темы

## 1. Логика хранения данных в сторе

### 1.1. Общая структура `TopicData`

В сторе темы (`topicStore`) данные лежат в `data`:

- **`theme`** — описание темы: название, описание, языки, списки терминов темы (`keywords`, `requiredWords`, `excludedWords`). Это «исходник» темы, с которым работает вкладка «Тема».
- **`search`** — всё, что относится к конструктору запросов: **пулы терминов** и **массив из четырёх слотов запросов**.
- **`sources`**, **`entities`**, **`events`** — остальные данные темы (источники, сущности, события).

### 1.2. SearchData: пулы и слоты запросов

```ts
search: {
  keywordTerms: Term[]   // пул ключевых слов (общий для всех запросов)
  mustTerms: Term[]     // пул обязательных слов
  excludeTerms: Term[]  // пул минус-слов
  queries: [SavedQuery, SavedQuery | null, SavedQuery | null, SavedQuery | null]
  isEditingDraft: boolean
  editingQueryIndex: 1 | 2 | 3 | null
}
```

- **Пулы** (`keywordTerms`, `mustTerms`, `excludeTerms`) — единый набор терминов темы для поиска. Термины добавляются сюда (вручную или из AI), хранятся с `id`, текстом, контекстом, переводами. Пулы **общие** для всех запросов: один и тот же термин может участвовать в разных запросах по ссылке на `id`.
- **`queries[0]`** — всегда **черновик** текущего запроса (редактируемый).
- **`queries[1]`, `queries[2]`, `queries[3]`** — до трёх **сохранённых** запросов; слот может быть `null`.
- **`editingQueryIndex`** — при редактировании сохранённого запроса: какой из слотов 1–3 редактируется; черновик тогда — копия этого запроса.
- **`isEditingDraft`** — флаг «черновик изменён после последнего сохранения» (для предупреждения при уходе со страницы).

### 1.3. Формат запроса (SavedQuery)

Запрос хранит **только ссылки на термины** (`id`), без дублирования самих слов:

- **`keywords`** — группы ключевых слов: массив групп `{ id, op: 'OR'|'AND', termIds }` и массив коннекторов между группами (`connectors`).
- **`must`** — `{ mode: 'ALL'|'ANY', termIds }` — обязательные слова и режим (все / любое).
- **`exclude`** — `{ termIds }` — минус-слова.

Текст запроса в UI собирается по этим `termIds` из пулов (функция `compileQueryPreviewFromSaved` в `queryBuilder.ts`).

---

## 2. Конструктор запросов: функциональная логика

### 2.1. Источники терминов

- Термины попадают в **пулы** при:
  - ручном добавлении в конструкторе (поле «Добавить ключевое/обязательное/минус-слово»);
  - применении AI-предложений по описанию темы (`applyThemeSuggestions`);
  - загрузке темы (`loadTopicIntoStore`).

Дубликаты по тексту (без учёта регистра) не добавляются.

### 2.2. «Неиспользуемые» vs «в запросе»

- **Неиспользуемые** — термины из пула, которых **нет** в текущем черновике запроса:
  - ключевые: не входят ни в одну группу `draft.keywords.groups`;
  - обязательные: не входят в `draft.must.termIds`;
  - минус: не входят в `draft.exclude.termIds`.
- В UI они вычисляются функциями `getUnusedKeywordTerms`, `getUnusedMustTerms`, `getUnusedExcludeTerms` (пулы + черновик).
- **В запросе** — термины, чьи `id` перечислены в черновике; для отображения берутся объекты из пулов по `id`.

### 2.3. Действия пользователя и изменение состояния

- **Добавить термин в пул** — `addSearchKeyword` / `addSearchMustTerm` / `addSearchExcludeTerm`: новый термин с уникальным `id` добавляется в соответствующий пул; в черновик он не попадает автоматически (кроме случая «черновик по умолчанию» при загрузке/предложении).
- **Ключевые слова**: «В группу» — `moveKeywordToGroup(termId, groupIndex)` (добавляет `termId` в выбранную группу черновика); «в неиспользуемые» — `moveKeywordToUnused` (удаляет из всех групп). Группы и коннекторы меняются через `setDraftKeywordGroupOp`, `setDraftConnector`, `addDraftKeywordGroup`, `removeDraftKeywordGroup`.
- **Обязательные / минус**: «В запрос» — `moveMustToGroup` / `moveExcludeToGroup`; «в неиспользуемые» — `moveMustToUnused` / `moveExcludeToUnused`. Режим MUST — `setDraftMustMode('ALL'|'ANY')`.
- **Сохранить запрос** — `saveCurrentQuery`: черновик копируется в слот 1, 2 или 3 (первый свободный или текущий при редактировании); выставляются `editingQueryIndex` и сброс «грязного» черновика.
- **Новый запрос** — `newQueryAfterConfirm`: черновик заменяется на «пустой» черновик по умолчанию (все термины из пулов снова в неиспользуемых/в запросе по умолчанию); при необходимости перед этим сохраняется текущий редактируемый запрос.
- **Редактировать сохранённый** — `startEditingQuery(index)`: запрос из слота 1–3 копируется в слот 0 (черновик), `editingQueryIndex = index`.
- **Удалить сохранённый** — `deleteSavedQuery(index)`: слот обнуляется, остальные сдвигаются, индексы редактирования корректируются.

Черновик всегда один — это `queries[0]`; при любом действии в конструкторе обновляется только он (и при сохранении — один из слотов 1–3).

---

## 3. Укрупнённая картина по коду

### 3.1. Стор (`topicStore.ts`)

- **Типы**: `SearchData`, `TopicData`, `TopicTheme`; импорт `SavedQuery`, `TermPools`, `KeywordGroupData` и хелперов из `queryBuilder`.
- **Инициализация search**: `getInitialSearch()` — пустые пулы, `queries = [createEmptyQuery(), null, null, null]`, флаги редактирования сброшены.
- **Синхронизация с темой**: при `applyThemeSuggestions` и `loadTopicIntoStore` пулы заполняются из темы (или из ответа API), черновик при необходимости строится через `getDefaultDraft(pools)` (все термины из пулов «в запросе» по умолчанию).
- **Обновление черновика**: все изменения конструктора идут через `setSearchDraft(updater)` или точечные экшены (`moveKeywordToGroup`, `setDraftMustMode` и т.д.), которые внутри делают `set` с новым `queries[0]` и при необходимости помечают `isEditingDraft`.
- **Сохранение/новый/редактирование/удаление** — отдельные экшены, которые переставляют и копируют элементы `queries` и обновляют `editingQueryIndex` / `isEditingDraft`.

### 3.2. Типы и хелперы (`queryBuilder.ts`)

- **SavedQuery**, **KeywordGroupData**, **TermPools** — контракт данных запроса и пулов.
- **createEmptyQuery**, **getDefaultDraft(pools)** — создание пустого запроса и черновика «всё из пулов в запросе».
- **compileQueryPreviewFromSaved(pools, query)** — сбор строки превью запроса по `termIds` и пулам (группы, MUST, NOT).
- **getUsedKeywordIds**, **getUnusedKeywordTerms**, **getUnusedMustTerms**, **getUnusedExcludeTerms** — вычисление «кто в запросе / кто неиспользуемый» по пулам и черновику.

### 3.3. UI (`ThemePage.tsx`)

- Берёт из стора: `theme`, `search` (пулы, `queries`, флаги редактирования).
- Строит **локальные производные**:
  - `draft = search.queries[0]`, `pools = { keywordTerms, mustTerms, excludeTerms }`;
  - `unusedKeywords`, `unusedMust`, `unusedExclude` — через функции из `queryBuilder`;
  - `mustTermsInQuery`, `excludeTermsInQuery` — объекты терминов по `draft.must.termIds` / `draft.exclude.termIds` из пулов;
  - `keywordGroupsTerms` — по группам черновика массив массивов терминов из пула;
  - `queryPreview` — `compileQueryPreviewFromSaved(pools, draft)`;
  - `savedQueries` — превью текстов для `queries[1..3]`.
- Обработчики вызывают экшены стора (`addSearchKeyword`, `moveMustToGroup`, `saveCurrentQuery` и т.д.); модалка редактирования термина — `updateSearchTermInPool`.
- Блокировка ухода при несохранённом черновике и диалоги «Новый запрос» / «Удалить запрос» завязаны на `search.isEditingDraft` и `search.editingQueryIndex`.

Итого: **пулы и массив из четырёх слотов запросов** в сторе — единственный источник правды; «неиспользуемые» и превью — производные от пулов и черновика, считаются в UI при каждом рендере по хелперам из `queryBuilder`.
