"""
File-based провайдер промптов: загрузка *.md из директории, YAML front matter, алиасы.
Lazy-load при первом обращении + кеш в памяти (PROMPT_CACHE_TTL_S=0 — навсегда).
"""
import asyncio
from pathlib import Path
from typing import Any

import yaml

from app.core.config import Settings
from app.integrations.prompts.ports import PromptProviderPort
from app.integrations.prompts.types import PromptTemplate, PromptTemplateMeta


def _project_root() -> Path:
    """Корень проекта (backend): app/integrations/prompts/providers -> backend."""
    return Path(__file__).resolve().parent.parent.parent.parent.parent


def _parse_front_matter(content: str) -> tuple[dict[str, Any], str]:
    """Разделить YAML front matter (между --- и ---) и body. Возвращает (meta_dict, body)."""
    if not content.strip().startswith("---"):
        return {}, content
    parts = content.strip().split("---", 2)
    if len(parts) < 3:
        return {}, content
    meta_str, body = parts[1].strip(), parts[2].strip()
    meta = yaml.safe_load(meta_str) if meta_str else {}
    return meta or {}, body


class FilePromptProvider:
    """Провайдер промптов из файловой системы: *.md с YAML front matter."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._root = _project_root()
        self._cache: dict[str, PromptTemplate] = {}
        self._alias_to_name: dict[str, str] = {}
        self._meta_list: list[PromptTemplateMeta] = []
        self._lock = asyncio.Lock()
        self._loaded = False

    async def _load_all(self) -> None:
        async with self._lock:
            if self._loaded:
                return
            prompts_dir = self._root / self._settings.PROMPT_FILES_DIR.strip()
            if not prompts_dir.is_dir():
                self._loaded = True
                return
            for path in prompts_dir.rglob("*.md"):
                try:
                    text = path.read_text(encoding="utf-8")
                except Exception:
                    continue
                meta, body = _parse_front_matter(text)
                name = meta.get("name")
                description = meta.get("description")
                if not name or not description:
                    continue
                version = meta.get("version")
                category = meta.get("category")
                response_format = meta.get("response_format") or "text"
                if response_format not in ("text", "json"):
                    response_format = "text"
                placeholders = meta.get("placeholders")
                if not isinstance(placeholders, list):
                    placeholders = []
                aliases = meta.get("aliases")
                if not isinstance(aliases, list):
                    aliases = []
                template = PromptTemplate(
                    name=name,
                    description=description,
                    version=version,
                    category=category,
                    response_format=response_format,
                    placeholders=placeholders,
                    aliases=aliases,
                    content=body,
                )
                self._cache[name] = template
                for al in aliases:
                    if al and al != name:
                        self._alias_to_name[al.strip()] = name
                self._meta_list.append(
                    PromptTemplateMeta(
                        name=name,
                        description=description,
                        version=version,
                        category=category,
                        response_format=response_format,
                        placeholders=placeholders,
                        aliases=aliases,
                    )
                )
            # Внешний файл алиасов
            aliases_file = self._settings.PROMPT_ALIASES_FILE.strip()
            if aliases_file:
                apath = self._root / aliases_file
                if apath.is_file():
                    try:
                        data = yaml.safe_load(apath.read_text(encoding="utf-8"))
                        if isinstance(data, dict):
                            for alias, canonical in data.items():
                                if canonical and alias:
                                    self._alias_to_name[str(alias).strip()] = str(canonical).strip()
                    except Exception:
                        pass
            self._meta_list.sort(key=lambda m: m.name)
            self._loaded = True

    def _resolve_name(self, name: str) -> str:
        return self._alias_to_name.get(name.strip(), name.strip())

    async def get(self, name: str) -> PromptTemplate:
        await self._load_all()
        canonical = self._resolve_name(name)
        if canonical not in self._cache:
            raise KeyError(f"Prompt not found: {name!r}")
        return self._cache[canonical]

    async def list(self, category: str | None = None) -> list[PromptTemplateMeta]:
        await self._load_all()
        if category is None:
            return list(self._meta_list)
        cat = category.strip().lower()
        return [m for m in self._meta_list if m.category and m.category.strip().lower() == cat]
