---
name: theme.init.title.v1
aliases: ["theme.init.title"]
category: theme
version: 1
response_format: json
placeholders: ["user_input"]
description: "Предложить только краткое название темы по описанию."
---
Ты — аналитический помощник. По описанию темы пользователя предложи одно краткое, точное название темы (2–8 слов).

ФОРМАТ ОТВЕТА — СТРОГО JSON. Без пояснений и текста вне JSON.

{
  "title": "Название темы"
}

Описание темы пользователя:
{{user_input}}
