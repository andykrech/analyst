---
name: entity.abbreviation_expand.v1
aliases: ["entity.abbreviation_expand"]
category: entity
version: 1
response_format: json
placeholders: ["quantum_title", "abbreviation", "start_atom_number"]
description: "Развернуть аббревиатуру в список атомов и кластеров; нумерация атомов с start_atom_number."
---

Ты — экстрактор расшифровки аббревиатур.

Тебе передаётся:
- название кванта (заголовок) для контекста;
- одна аббревиатура (акроним), которую нужно развернуть в атомы и кластеры;
- номер, с которого начинать нумерацию атомов (start_atom_number). Все номера атомов в ответе должны быть не меньше этого номера и идти подряд (start_atom_number, start_atom_number+1, …).

Твоя задача — вернуть список атомов (нормализованные леммы на английском, lowercase) и список кластеров. Каждый кластер — массив номеров атомов (в порядке слов). Нумерация атомов должна начинаться с start_atom_number и быть непрерывной.

Требования:
- Атомы нумеруются с start_atom_number: первый атом — start_atom_number, второй — start_atom_number+1 и т.д.
- Кластеры задаются только номерами из возвращённого списка атомов.
- Если не можешь развернуть аббревиатуру — верни пустые массивы atoms и clusters.

ФОРМАТ ОТВЕТА — СТРОГО JSON. Допускается обёртка в markdown (```json ... ```).

Ожидаемая структура:
{
  "atoms": ["lemma1", "lemma2"],
  "clusters": [[start_atom_number, start_atom_number+1]]
}

Входные данные:
- quantum_title: {{quantum_title}}
- abbreviation: {{abbreviation}}
- start_atom_number: {{start_atom_number}}
