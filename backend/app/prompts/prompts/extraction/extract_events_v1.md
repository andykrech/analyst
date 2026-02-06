---
name: extraction.extract_events.v1
aliases: ["extraction.extract_events"]
category: extraction
version: 1
response_format: json
placeholders: ["theme_context", "sources_json"]
description: "Извлечение событий из источников по контексту темы."
---

По контексту темы и списку источников извлеки события (новости, релизы, изменения), релевантные теме.

Контекст темы:
{{theme_context}}

Источники (JSON):
{{sources_json}}

Верни строго JSON-массив объектов событий. Каждый объект: минимум поля с датой/временем, заголовком, источником, кратким описанием. Без markdown, без пояснений — только валидный JSON.

Пример формата:
[
  {"date": "...", "title": "...", "source": "...", "summary": "..."},
  ...
]
