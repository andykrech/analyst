---
name: overview.update.v1
aliases: ["overview.update"]
category: overview
version: 1
response_format: text
placeholders: ["theme_title", "previous_overview", "new_findings_bullets"]
description: "Обновление обзора темы с учётом предыдущего текста и новых находок."
---

Обнови обзор по теме «{{theme_title}}».

Текущий обзор:
{{previous_overview}}

Новые находки (список):
{{new_findings_bullets}}

Объедини предыдущий обзор с новыми данными: сохрани актуальное, добавь новое, убери устаревшее. Результат — связный текст обзора. Формат: обычный текст (не JSON).
