# Quanta (theme_quanta)

## Что такое «квант информации»

**Квант** — это атомарная, проверяемая кликом единица знания внутри **одной темы**.  
Кванты **не переиспользуются между темами** (каждая тема — изолированная зона знаний).

Ключевое отличие от прежней модели `source_links`: квант не просто «ссылка», а фиксированная сущность с:
- типом (`entity_kind`: `publication|patent|webpage`)
- заголовком/описанием
- кликабельным `verification_url`
- атрибутами и доказуемой дедупликацией **внутри темы**

## Как заполнять (для ретриверов)

Минимально обязательные поля:
- `theme_id`
- `entity_kind`
- `title`
- `summary_text`
- `verification_url`
- `source_system`
- `retriever_name`

Опционально (но сильно помогает дедупу/качеству):
- `identifiers` (например `doi`, `patent_number`)
- `canonical_url`
- `date_at`
- `matched_terms` / `matched_term_ids`
- `attrs` для типоспецифичных полей без миграций

## Правила дедупликации

Уникальность обеспечивается constraint'ом:
- `UNIQUE(theme_id, dedup_key)`

`dedup_key` строится так:
1) если в `identifiers` есть `doi` → `doi:<value>`
2) иначе если есть `patent_number` → `patent:<value>`
3) иначе если есть `canonical_url` → `url:<canonical_url>`
4) иначе → `fp:<fingerprint>`

`fingerprint` (fallback) считается как `sha256` от:
`entity_kind + normalized(title) + date_bucket(YYYY-MM) + source_system`

Политика при конфликте (безопасная):
- запись **не перезаписывается агрессивно**
- заполняются только NULL/пустые поля и пустые JSON-массивы/пустой `attrs`

