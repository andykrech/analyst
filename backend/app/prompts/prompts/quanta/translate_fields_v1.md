---
name: quanta.translate_fields.v1
aliases: ["quanta.translate_fields"]
category: quanta
version: 1
response_format: json
placeholders: ["target_language", "items"]
description: "Перевод полей квантов (title, summary_text, key_points) на основной язык темы."
---

Ты — аналитический помощник. Тебе дан массив объектов (информационных квантов): у каждого есть id, title, summary_text и key_points (список строк). Язык исходных текстов может быть любым.

Твоя задача — перевести для каждого объекта поля title, summary_text и key_points на язык {{target_language}}. Перевод должен сохранять смысл и быть естественным для целевого языка.

ТРЕБОВАНИЯ:
- Сохраняй строгое соответствие 1:1 по id: в ответе должен быть ровно один элемент для каждого id из входного списка, в том же порядке.
- Не добавляй и не пропускай id.
- title_translated — перевод заголовка (одна строка).
- summary_text_translated — перевод краткого описания (одна строка, можно много предложений).
- key_points_translated — массив строк, каждая строка — перевод соответствующего пункта из key_points; порядок и количество элементов сохрани.

ФОРМАТ ОТВЕТА — СТРОГО JSON. Без пояснений и текста вне JSON.

```json
{
  "translations": [
    {
      "id": "uuid или строка id кванта",
      "title_translated": "переведённый заголовок",
      "summary_text_translated": "переведённое описание",
      "key_points_translated": ["пункт 1", "пункт 2"]
    }
  ]
}
```

---

Входной массив объектов (JSON):
{{items}}
