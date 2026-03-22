---
name: event.extract_events_from_quantum_mvp.v1
aliases: ["event.extract_events_from_quantum_mvp"]
category: extraction
version: 1
response_format: json
placeholders: ["quantum_text", "entities_json", "plots_json"]
description: "MVP: извлечение событий (Event mention) из одного кванта."
---

Ты - помощник аналитика, который извлекает из текста события с заданной структурой, в которых участвуют определенные ранее объекты.

Центральным элементом любого события является глагол (он называется predicat в структуре событий), он говорит, что происходит.

Порядок работы:
- В каждом предложении найди выделенные ранее объекты (если они есть)
- Определи, есть ли глаголы, которые говорят о действиях этих объектов или над этими объектами. Это будут события.
- Если такие глаголы есть, определи, к какому типу структуры относятся эти события.
- Сформируй описание каждого найденного события в соответствии со структурой, включи в выходной список.

Входные данные:
- Текст (title+summary):
{{quantum_text}}

- Ранее найденные объекты в этом тексте (JSON). Каждый объект содержит entity_id и normalized_name.
{{entities_json}}

- Возможные структуры событий (JSON). Каждый сюжет: code, name, description, schema.
schema содержит:
- roles: возможные роли/элементы (включая специальный элемент "predicate")
- required_roles: обязательные роли/элементы (включая "predicate")
- attribute_targets: для каких элементов допустимы атрибуты ("subject|object|predicate|event|instrument|reason|speaker" и т.п.)
{{plots_json}}

Задача:
1) Если в кванте НЕТ событий — верни строго JSON: {"events": null}.
2) Если события есть — верни строго JSON: {"events": [ ... ]}

Для каждого события верни объект:
{
  "plot_code": "<code из event_plots>",
  "predicate_text": "<как в тексте: глагол/предикат>",
  "predicate_normalized": "<каноническая форма предиката на английском для группировки, используй максимально общий и стабильный глагол.>",
  "predicate_class": "<более общий класс на английском: investment/measurement/growth/ownership/claim/... Если не уверен - верни null>",
  "display_text": "<готовый человекочитаемый текст события для UI>",
  "event_time": "<текст времени/даты, если явно есть, иначе null>",
  "participants": [
     {"role": "<role code>", "entity_id": "<UUID сущности>"},
     ...
  ],
  "attributes": [
     {
       "attribute_for": "subject|object|predicate|event|instrument|reason|speaker",
       "entity_id": "<UUID сущности или null (для predicate/event)>",
       "attribute_text": "...",
       "attribute_normalized": "..." | null
     }
  ]
}

Правила:
- Извлекай только семантически независимые события. Не дроби одно событие на несколько, если они описывают одно действие
- Используй ТОЛЬКО entity_id из списка сущностей для участников и атрибутов.
- role в participants должен быть валидным кодом роли из event_roles (subject/object/instrument/reason/speaker),
  либо отсутствовать (не выдумывай новые роли).
- "predicate" НЕ является участником: предикат задаётся полями predicate_*.
- required_roles из schema должны быть удовлетворены:
  - если required_roles содержит "predicate", то predicate_text и predicate_normalized должны быть непустыми
  - прочие required_roles должны быть представлены среди participants (role + entity_id)
- attributes:
  - Атрибуты - это какие-либо характеристики, уточняющие описание элементов события.
  - Извлекай атрибуты только если они изменяют смысл события, задают условие / количество / стадию / режим / время
  - attribute_for указывает, к чему относится атрибут
  - если attribute_for относится к сущности (subject/object/instrument/reason/speaker), укажи entity_id этой сущности
  - если attribute_for = predicate или event, entity_id = null

Верни только валидный JSON. Без markdown, без пояснений.

