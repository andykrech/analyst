---
name: digest.weekly.v1
aliases: ["digest.weekly"]
category: digest
version: 1
response_format: text
placeholders: ["theme_title", "sources_bullets"]
description: "Еженедельный дайджест по теме на основе списка источников."
---

Подготовь еженедельный дайджест по теме «{{theme_title}}».

Ключевые материалы (список):
{{sources_bullets}}

Структура дайджеста:
- Краткое введение (1–2 абзаца).
- Основные события и тренды по пунктам.
- Выводы и рекомендации.

Формат: обычный текст (не JSON). Пиши ясно и по делу.
