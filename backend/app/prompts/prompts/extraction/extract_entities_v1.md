---
name: extraction.extract_entities.v1
aliases: ["extraction.extract_entities"]
category: extraction
version: 1
response_format: json
placeholders: ["theme_context", "sources_json"]
description: "Извлечение сущностей (компании, персоны, технологии) из источников."
---

По контексту темы и списку источников извлеки сущности: компании, персоны, технологии, продукты — релевантные теме.

Контекст темы:
{{theme_context}}

Источники (JSON):
{{sources_json}}

Верни строго JSON-массив объектов сущностей. Укажи тип (company, person, technology, product и т.д.), имя, опционально контекст. Без markdown, без пояснений — только валидный JSON.

Пример формата:
[
  {"type": "company", "name": "...", "context": "..."},
  ...
]
