"""
Экстрактор атомов и кластеров из summary_text кванта (v2.0).
Обрабатывает пакеты квантов с entity_extraction_version = null;
для каждого кванта: ИИ извлекает атомы/кластеры/аббревиатуры, резолв аббревиатур,
нормализация атомов и кластеров, запись в БД и relations.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from typing import Any, Optional

from sqlalchemy import func, select, text as sql_text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.llm import LLMService
from app.integrations.prompts import PromptService
from app.modules.entity.model import (
    Abbreviation,
    AbbreviationAtom,
    AbbreviationCluster,
    Atom,
    Cluster,
    ClusterAtom,
    ThemeStats,
)
from app.modules.quanta.models import Quantum
from app.modules.relation.model import Relation
from app.modules.theme.model import Theme

logger = logging.getLogger(__name__)

_ENTITY_DEBUG_LOG_PATH = "logs/events_llm_debug.log"


def _get_entity_debug_logger() -> logging.Logger:
    """Логгер для подробного вывода извлечения сущностей (тот же файл, что и для событий)."""
    dbg = logging.getLogger("events_llm_debug")
    if not dbg.handlers:
        dbg.setLevel(logging.INFO)
        try:
            os.makedirs(os.path.dirname(_ENTITY_DEBUG_LOG_PATH) or ".", exist_ok=True)
            fh = logging.FileHandler(_ENTITY_DEBUG_LOG_PATH, encoding="utf-8")
            fh.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
            dbg.addHandler(fh)
        except Exception as e:
            logger.warning("atoms_clusters_extractor: failed to init debug logger: %s", e)
    return dbg


PROMPT_EXTRACT = "entity.atoms_clusters_extract.v1"
PROMPT_ABBREVIATION_EXPAND = "entity.abbreviation_expand.v1"
PROMPT_CLUSTER_TYPE = "entity.cluster_type.v1"
PROMPT_ATOM_SPECIFICITY = "entity.atom_specificity.v1"
PROMPT_NAME_TRANSLATE = "entity.entities_name_translate.v1"

ENTITY_EXTRACTION_VERSION_V2 = "v2.0"

VALID_CLUSTER_TYPES = frozenset({"tech", "org", "object", "phenomenon"})

# Базовый набор английских предлогов, которые не считаем атомами
EN_PREPOSITIONS = frozenset(
    {
        "of",
        "in",
        "on",
        "at",
        "for",
        "to",
        "by",
        "with",
        "from",
        "about",
        "over",
        "under",
        "between",
        "into",
        "through",
        "during",
        "before",
        "after",
        "without",
        "within",
        "along",
        "across",
        "behind",
        "beyond",
        "around",
        "near",
        "inside",
        "outside",
        "upon",
    }
)


def _strip_json_markdown(raw: str) -> str:
    """Убрать обёртку ```json ... ``` для корректного парсинга JSON."""
    s = (raw or "").strip()
    if not s:
        return s
    if s.startswith("```"):
        lines = s.splitlines()
        if lines and re.match(r"^```\s*json\s*$", lines[0].strip(), re.IGNORECASE):
            lines = lines[1:]
        elif lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    return s


def _normalize_lemma(s: str) -> str:
    """Нормализация леммы: lowercase, схлопнуть пробелы."""
    if not s or not isinstance(s, str):
        return ""
    return re.sub(r"\s+", " ", s.strip()).lower()


def _theme_primary_language(theme: Theme | None) -> str:
    if not theme:
        return "en"
    langs = theme.languages or []
    if isinstance(langs, list) and len(langs) > 0 and isinstance(langs[0], str):
        first = (langs[0] or "").strip()
        if first:
            return first
    return "en"


def _is_english(lang: str | None) -> bool:
    if not lang:
        return True
    return (lang or "").strip().lower() in ("en", "eng", "english")


class AtomsClustersExtractor:
    """Экстрактор атомов и кластеров из квантов (v2.0): summary_text → ИИ → atoms/clusters/abbreviations."""

    def __init__(self, llm_service: LLMService, prompt_service: PromptService) -> None:
        self._llm = llm_service
        self._prompt = prompt_service

    async def process_next_batch(
        self,
        session: AsyncSession,
        *,
        theme_id: Optional[Any] = None,
        batch_size: int = 20,
        debug_log: bool = False,
        stop_after_first_prompt: bool = False,
    ) -> int:
        """
        Обработать квант(ы) с entity_extraction_version = null.
        stop_after_first_prompt: для отладки — после первого ответа ИИ логировать и выйти, в БД ничего не писать.
        """
        stmt = (
            select(Quantum)
            .where(Quantum.entity_extraction_version.is_(None))
            .order_by(Quantum.created_at)
            .with_for_update(skip_locked=True)
        )
        if theme_id is not None:
            stmt = stmt.where(Quantum.theme_id == theme_id)
        result = await session.execute(stmt)
        quanta = list(result.scalars().all())
        if not quanta:
            return 0

        for q in quanta:
            try:
                await self._process_one_quantum(
                    session,
                    q,
                    debug_log=debug_log,
                    stop_after_first_prompt=stop_after_first_prompt,
                )
            except Exception as e:
                logger.exception(
                    "atoms_clusters_extractor: failed for quantum_id=%s: %s",
                    q.id,
                    e,
                )
                continue

        if not stop_after_first_prompt:
            await session.execute(
                update(Quantum)
                .where(Quantum.id.in_([q.id for q in quanta]))
                .values(entity_extraction_version=ENTITY_EXTRACTION_VERSION_V2)
            )
            await session.flush()

            # После обработки батча пересчитываем global_score для атомов и кластеров по затронутым темам.
            theme_ids = {q.theme_id for q in quanta if q.theme_id}
            if theme_id is not None:
                theme_ids = {theme_id}
            for tid in theme_ids:
                await self._recalculate_atom_scores_for_theme(session, tid)
                await self._recalculate_cluster_scores_for_theme(session, tid)
            await session.flush()
        return len(quanta)

    async def _process_one_quantum(
        self,
        session: AsyncSession,
        quantum: Quantum,
        *,
        debug_log: bool = False,
        stop_after_first_prompt: bool = False,
    ) -> None:
        theme_id = quantum.theme_id
        summary = (quantum.summary_text or "").strip()
        dbg = _get_entity_debug_logger() if debug_log else None
        atoms_added: list[str] = []
        clusters_added: list[tuple[str, str]] = []  # (normalized_text, type)
        abbreviations_added: list[str] = []

        if not summary:
            await session.execute(
                update(Quantum).where(Quantum.id == quantum.id).values(entity_extraction_version=ENTITY_EXTRACTION_VERSION_V2)
            )
            await session.flush()
            return

        if dbg:
            dbg.info(
                "========== ENTITY EXTRACT (v2) quantum_id=%s theme_id=%s title=%s ==========",
                quantum.id,
                theme_id,
                (quantum.title or "")[:80],
            )

        # 1) ИИ: атомы, кластеры, аббревиатуры
        if dbg:
            rendered = await self._prompt.render(PROMPT_EXTRACT, {"summary_text": summary})
            dbg.info("ENTITY PROMPT [%s]:\n%s", PROMPT_EXTRACT, rendered.text or "")
        response = await self._llm.generate_from_prompt(
            PROMPT_EXTRACT,
            {"summary_text": summary},
            self._prompt,
        )
        raw = (response.text or "").strip()
        if dbg:
            dbg.info("ENTITY RESPONSE [%s]:\n%s", PROMPT_EXTRACT, raw or "(empty)")
        if stop_after_first_prompt:
            if dbg:
                dbg.info("ENTITY EXTRACT (debug): остановка после первого промпта, в БД не пишем.")
            return
        if not raw:
            logger.warning("atoms_clusters_extractor: empty LLM response for quantum_id=%s", quantum.id)
            await session.execute(
                update(Quantum).where(Quantum.id == quantum.id).values(entity_extraction_version=ENTITY_EXTRACTION_VERSION_V2)
            )
            await session.flush()
            return

        text_for_json = _strip_json_markdown(raw)
        try:
            data = json.loads(text_for_json)
        except json.JSONDecodeError as e:
            logger.warning("atoms_clusters_extractor: invalid JSON quantum_id=%s: %s", quantum.id, e)
            return

        # clusters: список строк (терминов), abbreviations: список акронимов
        clusters_raw = data.get("clusters") or []
        abbreviations_raw: list[str] = data.get("abbreviations") or []
        if not isinstance(clusters_raw, list):
            clusters_raw = []
        if not isinstance(abbreviations_raw, list):
            abbreviations_raw = []

        cluster_strings: list[str] = []
        for c in clusters_raw:
            if isinstance(c, str):
                s = c.strip()
                if s:
                    cluster_strings.append(s)

        q_lang = (quantum.language or "").strip() or None
        is_english = _is_english(q_lang)
        theme = await session.get(Theme, theme_id)
        primary_lang = _theme_primary_language(theme)

        # 2) Если язык не английский — сразу переводим кластеры на английский
        # Атомы отдельно не переводим, будем выделять их уже из английских кластеров.
        if not is_english:
            src = q_lang or "auto"
            translated_clusters: list[str] = []
            for phrase in cluster_strings:
                tr = await self._translate(
                    session,
                    term=phrase,
                    source_language=src,
                    target_language="en",
                    dbg=dbg,
                )
                translated_clusters.append(_normalize_lemma(tr or phrase))
            cluster_strings_en = translated_clusters
            # Аббревиатуры для неанглийских игнорируем
            abbreviations_raw = []
        else:
            # Английский квант — просто нормализуем кластеры
            cluster_strings_en = [_normalize_lemma(c) for c in cluster_strings if _normalize_lemma(c)]

        # 3) Выделение атомов из английских кластеров, отбрасывая предлоги
        atoms_list: list[str] = []
        # Кандидаты: атомы (по лемме) и кластеры (по кортежу (lemma_1, lemma_2, ...))
        candidate_atoms: set[str] = set()
        candidate_clusters_with_count: Counter[tuple[str, ...]] = Counter()
        # Для неанглийских тем, когда язык кванта совпадает с основным языком темы,
        # сохраняем вариант написания для display_name.
        cluster_display_overrides: dict[tuple[str, ...], str] = {}

        for idx, phrase_en in enumerate(cluster_strings_en):
            if not phrase_en:
                continue
            tokens = phrase_en.split()
            lemmas_here: list[str] = []
            for t in tokens:
                lemma = _normalize_lemma(t)
                if not lemma:
                    continue
                # Предлоги выкидываем только если это отдельное слово, не часть дефисного слова (in-situ).
                if "-" not in t and lemma in EN_PREPOSITIONS:
                    continue
                lemmas_here.append(lemma)
            if not lemmas_here:
                continue
            atoms_list.extend(lemmas_here)
            key = tuple(lemmas_here)
            candidate_atoms.update(lemmas_here)
            candidate_clusters_with_count[key] += 1

            # Если язык кванта совпадает с основным языком темы и он не английский —
            # запомним оригинальное написание кластера для display_name.
            if not is_english and primary_lang and q_lang and primary_lang.lower() == q_lang.lower() and not _is_english(primary_lang):
                if idx < len(cluster_strings):
                    original_phrase = cluster_strings[idx]
                    cluster_display_overrides.setdefault(key, original_phrase)

        if dbg and candidate_atoms:
            dbg.info("ENTITY ATOMS (normalized, no prepositions): %s", sorted(candidate_atoms))

        # 4) Аббревиатуры (только для английского)
        n_atoms = len(atoms_list)
        start_atom_number = n_atoms + 1
        abbr_to_expansion: dict[str, list[str]] = {}
        for abbr in abbreviations_raw:
            if not isinstance(abbr, str) or not (abbr or "").strip():
                continue
            abbr_clean = (abbr or "").strip()
            # Есть ли в БД?
            existing_abbr = await session.execute(
                select(Abbreviation).where(
                    Abbreviation.theme_id == theme_id,
                    Abbreviation.abbreviation == abbr_clean,
                )
            )
            row = existing_abbr.scalar_one_or_none()
            if row:
                # Подгрузить атомы и кластеры этой аббревиатуры
                aa = await session.execute(select(AbbreviationAtom).where(AbbreviationAtom.abbreviation_id == row.id))
                expansion_lemmas: list[str] = []
                for link in aa.scalars().all():
                    atom = await session.get(Atom, link.atom_id)
                    if atom and atom.lemma:
                        candidate_atoms.add(atom.lemma)
                        expansion_lemmas.append(atom.lemma)
                ac = await session.execute(select(AbbreviationCluster).where(AbbreviationCluster.abbreviation_id == row.id))
                for link in ac.scalars().all():
                    cluster = await session.get(Cluster, link.cluster_id)
                    if cluster:
                        ca_list = await session.execute(
                            select(ClusterAtom).where(ClusterAtom.cluster_id == cluster.id).order_by(ClusterAtom.position)
                        )
                        atom_ids = [r.atom_id for r in ca_list.scalars().all()]
                        lemmas = []
                        for aid in atom_ids:
                            a = await session.get(Atom, aid)
                            if a and a.lemma:
                                lemmas.append(a.lemma)
                        if lemmas:
                            candidate_clusters_with_count[tuple(lemmas)] += 1
                abbr_lemma = _normalize_lemma(abbr_clean)
                if abbr_lemma and expansion_lemmas:
                    abbr_to_expansion[abbr_lemma] = expansion_lemmas
                continue

            start_used = start_atom_number
            abbr_vars = {
                "quantum_title": (quantum.title or "")[:500],
                "abbreviation": abbr_clean,
                "start_atom_number": start_used,
            }
            if dbg:
                rendered_abbr = await self._prompt.render(PROMPT_ABBREVIATION_EXPAND, abbr_vars)
                dbg.info("ENTITY PROMPT [%s] abbreviation=%s:\n%s", PROMPT_ABBREVIATION_EXPAND, abbr_clean, rendered_abbr.text or "")
            response_abbr = await self._llm.generate_from_prompt(
                PROMPT_ABBREVIATION_EXPAND,
                abbr_vars,
                self._prompt,
            )
            if dbg:
                dbg.info("ENTITY RESPONSE [%s]:\n%s", PROMPT_ABBREVIATION_EXPAND, (response_abbr.text or "").strip())
            raw_abbr = _strip_json_markdown((response_abbr.text or "").strip())
            if not raw_abbr:
                continue
            try:
                data_abbr = json.loads(raw_abbr)
            except json.JSONDecodeError:
                continue
            abbr_atoms = [_normalize_lemma(a) for a in (data_abbr.get("atoms") or []) if isinstance(a, str) and _normalize_lemma(a)]
            abbr_clusters_raw = data_abbr.get("clusters") or []
            if not abbr_atoms:
                continue

            for lemma in abbr_atoms:
                await self._get_or_create_atom(session, theme_id, lemma, atoms_added=atoms_added if dbg else None)
            start_atom_number += len(abbr_atoms)
            candidate_atoms.update(abbr_atoms)
            abbr_lemma = _normalize_lemma(abbr_clean)
            if abbr_lemma and abbr_atoms:
                abbr_to_expansion[abbr_lemma] = abbr_atoms

            for c in abbr_clusters_raw:
                if not isinstance(c, list):
                    continue
                lemmas_here = []
                for num in c:
                    if isinstance(num, (int, float)):
                        idx = int(num) - start_used
                        if 0 <= idx < len(abbr_atoms):
                            lemmas_here.append(abbr_atoms[idx])
                if lemmas_here:
                    candidate_clusters_with_count[tuple(lemmas_here)] += 1

            new_abbr = Abbreviation(theme_id=theme_id, abbreviation=abbr_clean)
            session.add(new_abbr)
            await session.flush()
            if dbg:
                abbreviations_added.append(abbr_clean)
            for lemma in abbr_atoms:
                aid = (await session.execute(select(Atom).where(Atom.theme_id == theme_id, Atom.lemma == lemma))).scalar_one().id
                session.add(AbbreviationAtom(abbreviation_id=new_abbr.id, atom_id=aid))
            abbr_cluster_keys = set()
            for c in abbr_clusters_raw:
                if not isinstance(c, list):
                    continue
                lemmas_here = []
                for num in c:
                    if isinstance(num, (int, float)):
                        idx = int(num) - start_used
                        if 0 <= idx < len(abbr_atoms):
                            lemmas_here.append(abbr_atoms[idx])
                if lemmas_here:
                    abbr_cluster_keys.add(tuple(lemmas_here))
            for key in abbr_cluster_keys:
                cluster_entity = await self._get_or_create_cluster_for_quantum(
                    session,
                    theme_id,
                    list(key),
                    quantum,
                    count=1,
                    clusters_added=clusters_added if dbg else None,
                    dbg=dbg,
                )
                if cluster_entity:
                    session.add(AbbreviationCluster(abbreviation_id=new_abbr.id, cluster_id=cluster_entity.id))
            await session.flush()

        # 5) После обработки аббревиатур: заменить аббревиатуры в кластерах на расшифровку
        if abbr_to_expansion:
            expanded_clusters_with_count: Counter[tuple[str, ...]] = Counter()
            for cluster_key, cnt in candidate_clusters_with_count.items():
                expanded: list[str] = []
                for lemma in cluster_key:
                    if lemma in abbr_to_expansion:
                        expanded.extend(abbr_to_expansion[lemma])
                    else:
                        expanded.append(lemma)
                if expanded:
                    expanded_clusters_with_count[tuple(expanded)] += cnt
            candidate_clusters_with_count = expanded_clusters_with_count

            # Удаляем аббревиатурные атомы и добавляем атомы расшифровок
            for abbr_lemma, exp_lemmas in abbr_to_expansion.items():
                candidate_atoms.discard(abbr_lemma)
                for l in exp_lemmas:
                    if l:
                        candidate_atoms.add(l)

        # 6) Батчевое определение типов уникальных кластеров через ИИ (один запрос на квант)
        cluster_type_by_key: dict[tuple[str, ...], str] = {}
        unique_cluster_keys = list(candidate_clusters_with_count.keys())
        if unique_cluster_keys:
            type_vars = {
                "quantum_title": (quantum.title or "")[:500],
                "clusters_json": json.dumps([" ".join(k) for k in unique_cluster_keys], ensure_ascii=False),
            }
            if dbg:
                rendered_type = await self._prompt.render(PROMPT_CLUSTER_TYPE, type_vars)
                dbg.info("ENTITY PROMPT [%s]:\n%s", PROMPT_CLUSTER_TYPE, rendered_type.text or "")
            type_response = await self._llm.generate_from_prompt(
                PROMPT_CLUSTER_TYPE,
                type_vars,
                self._prompt,
            )
            if dbg:
                dbg.info("ENTITY RESPONSE [%s]:\n%s", PROMPT_CLUSTER_TYPE, (type_response.text or "").strip())
            type_raw = _strip_json_markdown((type_response.text or "").strip())
            types: list[str] = []
            if type_raw:
                try:
                    payload = json.loads(type_raw)
                    maybe_types = payload.get("types") if isinstance(payload, dict) else None
                    if isinstance(maybe_types, list):
                        types = [str(x).strip().lower() for x in maybe_types]
                except json.JSONDecodeError:
                    types = []
            for i, key in enumerate(unique_cluster_keys):
                t = types[i] if i < len(types) else "other"
                cluster_type_by_key[key] = t if t in VALID_CLUSTER_TYPES else "other"

        # 7) Уникальные атомы: получить/создать в БД; для новых — оценка специфичности
        unique_atoms = sorted(candidate_atoms)
        lemma_to_atom_id: dict[str, Any] = {}
        new_lemmas: list[str] = []
        for lemma in unique_atoms:
            atom_id = await self._get_or_create_atom(session, theme_id, lemma, atoms_added=atoms_added if dbg else None)
            lemma_to_atom_id[lemma] = atom_id
            existing = await session.execute(select(Atom).where(Atom.id == atom_id))
            a = existing.scalar_one()
            if a.specificity_score is None:
                new_lemmas.append(lemma)

        if new_lemmas:
            spec_vars = {"atoms_json": json.dumps(new_lemmas, ensure_ascii=False)}
            if dbg:
                rendered_spec = await self._prompt.render(PROMPT_ATOM_SPECIFICITY, spec_vars)
                dbg.info("ENTITY PROMPT [%s]:\n%s", PROMPT_ATOM_SPECIFICITY, rendered_spec.text or "")
            spec_response = await self._llm.generate_from_prompt(
                PROMPT_ATOM_SPECIFICITY,
                spec_vars,
                self._prompt,
            )
            if dbg:
                dbg.info("ENTITY RESPONSE [%s]:\n%s", PROMPT_ATOM_SPECIFICITY, (spec_response.text or "").strip())
            spec_raw = _strip_json_markdown((spec_response.text or "").strip())
            if spec_raw:
                try:
                    spec_data = json.loads(spec_raw)
                    scores: list[float] = spec_data.get("scores") or []
                    for i, lemma in enumerate(new_lemmas):
                        if i < len(scores) and isinstance(scores[i], (int, float)):
                            score = float(scores[i])
                            if 0 <= score <= 1:
                                await session.execute(
                                    update(Atom)
                                    .where(Atom.theme_id == theme_id, Atom.lemma == lemma)
                                    .values(specificity_score=score)
                                )
                except (json.JSONDecodeError, TypeError):
                    pass
        await session.flush()

        # 8) Уникальные кластеры: получить/создать кластер, обновить global_df/global_score
        for cluster_key, count in candidate_clusters_with_count.items():
            await self._get_or_create_cluster_for_quantum(
                session,
                theme_id,
                list(cluster_key),
                quantum,
                count=count,
                clusters_added=clusters_added if dbg else None,
                dbg=dbg,
                display_text_override=cluster_display_overrides.get(cluster_key),
                cluster_type=cluster_type_by_key.get(cluster_key),
            )
        await session.flush()

        # 9) Relations: кластер → квант (mentions) — по одному разу на уникальный кластер в этом кванте
        for cluster_key in candidate_clusters_with_count:
            cluster_entity = await session.execute(
                select(Cluster).where(
                    Cluster.theme_id == theme_id,
                    Cluster.normalized_text == " ".join(cluster_key),
                )
            )
            c = cluster_entity.scalar_one_or_none()
            if c:
                await session.execute(
                    insert(Relation)
                    .values(
                        theme_id=theme_id,
                        subject_type="cluster",
                        subject_id=c.id,
                        object_type="quantum",
                        object_id=quantum.id,
                        relation_type="mentions",
                        direction="forward",
                        status="active",
                        is_user_created=False,
                    )
                    .on_conflict_do_nothing(
                        index_elements=[
                            "theme_id", "subject_type", "subject_id",
                            "relation_type", "object_type", "object_id",
                        ],
                        index_where=sql_text("deleted_at IS NULL AND status = 'active'"),
                    )
                )
        await session.flush()

        # 10) Атомы: увеличить global_cluster_df на число вхождений в кластеры (с учётом кратности кластеров)
        atom_contrib: Counter[str] = Counter()
        for cluster_key, cnt in candidate_clusters_with_count.items():
            for lemma in cluster_key:
                atom_contrib[lemma] += cnt
        stats = await self._get_or_create_theme_stats(session, theme_id)
        for lemma, delta in atom_contrib.items():
            atom_id = lemma_to_atom_id.get(lemma)
            if not atom_id:
                continue
            existing = await session.execute(select(Atom).where(Atom.id == atom_id))
            atom = existing.scalar_one()
            new_df = (atom.global_cluster_df or 0) + delta
            await session.execute(update(Atom).where(Atom.id == atom_id).values(global_cluster_df=new_df))
            if (stats.max_atom_cluster_df or 0) < new_df:
                await session.execute(
                    update(ThemeStats).where(ThemeStats.id == stats.id).values(max_atom_cluster_df=new_df)
                )
                stats.max_atom_cluster_df = new_df
        await session.flush()
        max_atom_df = stats.max_atom_cluster_df or 1
        for lemma in atom_contrib:
            atom_id = lemma_to_atom_id.get(lemma)
            if not atom_id:
                continue
            existing = await session.execute(select(Atom).where(Atom.id == atom_id))
            atom = existing.scalar_one()
            spec = atom.specificity_score if atom.specificity_score is not None else 1.0
            new_score = spec * (atom.global_cluster_df or 0) / max_atom_df
            await session.execute(update(Atom).where(Atom.id == atom_id).values(global_score=new_score))
        await session.flush()

        if dbg:
            dbg.info(
                "ENTITY DB: atoms_added=%s clusters_added=%s abbreviations_added=%s",
                atoms_added,
                clusters_added,
                abbreviations_added,
            )
            dbg.info("========== END ENTITY EXTRACT quantum_id=%s ==========", quantum.id)

    async def _translate(
        self,
        session: AsyncSession,
        *,
        term: str,
        source_language: str,
        target_language: str,
        dbg: Optional[logging.Logger] = None,
    ) -> Optional[str]:
        t = (term or "").strip()
        if not t:
            return None
        vars_map = {
            "term": t,
            "source_language": source_language or "auto",
            "target_language": target_language or "en",
        }
        if dbg:
            rendered = await self._prompt.render(PROMPT_NAME_TRANSLATE, vars_map)
            dbg.info("ENTITY PROMPT [%s] term=%r:\n%s", PROMPT_NAME_TRANSLATE, t[:60], rendered.text or "")
        try:
            r = await self._llm.generate_from_prompt(PROMPT_NAME_TRANSLATE, vars_map, self._prompt)
            out = (r.text or "").strip()
            if dbg:
                dbg.info("ENTITY RESPONSE [%s] term=%r -> %s", PROMPT_NAME_TRANSLATE, t[:60], out[:100] if out else "(empty)")
            return out if out else None
        except Exception as e:
            logger.warning("atoms_clusters_extractor: translate failed term=%r: %s", t[:50], e)
            return None

    async def _get_or_create_atom(
        self,
        session: AsyncSession,
        theme_id: Any,
        lemma: str,
        *,
        atoms_added: Optional[list[str]] = None,
    ) -> Any:
        existing = await session.execute(
            select(Atom).where(Atom.theme_id == theme_id, Atom.lemma == lemma)
        )
        row = existing.scalar_one_or_none()
        if row:
            return row.id
        a = Atom(theme_id=theme_id, lemma=lemma, global_cluster_df=0, global_score=0.0)
        session.add(a)
        await session.flush()
        if atoms_added is not None:
            atoms_added.append(lemma)
        return a.id

    async def _get_or_create_theme_stats(self, session: AsyncSession, theme_id: Any) -> ThemeStats:
        existing = await session.execute(
            select(ThemeStats).where(ThemeStats.theme_id == theme_id).order_by(ThemeStats.id).limit(1)
        )
        row = existing.scalar_one_or_none()
        if row:
            return row
        st = ThemeStats(theme_id=theme_id, max_cluster_df=0, max_atom_cluster_df=0)
        session.add(st)
        await session.flush()
        return st

    async def _get_or_create_cluster_for_quantum(
        self,
        session: AsyncSession,
        theme_id: Any,
        lemmas: list[str],
        quantum: Quantum,
        *,
        count: int = 1,
        clusters_added: Optional[list[tuple[str, str]]] = None,
        dbg: Optional[logging.Logger] = None,
        display_text_override: Optional[str] = None,
        cluster_type: Optional[str] = None,
    ) -> Optional[Cluster]:
        cluster_translation_needed = False
        if not lemmas:
            return None
        normalized_text = " ".join(lemmas)
        existing = await session.execute(
            select(Cluster).where(
                Cluster.theme_id == theme_id,
                Cluster.normalized_text == normalized_text,
            )
        )
        stats = await self._get_or_create_theme_stats(session, theme_id)
        c = existing.scalar_one_or_none()
        if c:
            new_df = (c.global_df or 0) + count
            await session.execute(update(Cluster).where(Cluster.id == c.id).values(global_df=new_df))
            max_cdf = stats.max_cluster_df or 0
            if max_cdf < new_df:
                await session.execute(
                    update(ThemeStats).where(ThemeStats.id == stats.id).values(max_cluster_df=new_df)
                )
                max_cdf = new_df
            await session.flush()
            new_score = new_df / (max_cdf or 1)
            await session.execute(update(Cluster).where(Cluster.id == c.id).values(global_score=new_score))
            return c

        # Новый кластер: тип приходит батчем (если не пришёл — other)
        ct = (cluster_type or "").strip().lower() if cluster_type else "other"
        if ct not in VALID_CLUSTER_TYPES:
            ct = "other"

        theme = await session.get(Theme, theme_id)
        primary_lang = _theme_primary_language(theme)
        display_text = normalized_text
        if display_text_override:
            display_text = display_text_override
        elif cluster_translation_needed and primary_lang and primary_lang.lower() != "en":
            tr = await self._translate(
                session,
                term=normalized_text,
                source_language="en",
                target_language=primary_lang,
                dbg=dbg,
            )
            if tr:
                display_text = tr

        if clusters_added is not None:
            clusters_added.append((normalized_text, ct))
        new_cluster = Cluster(
            theme_id=theme_id,
            normalized_text=normalized_text,
            display_text=display_text,
            type=ct,
            global_df=count,
            global_score=0.0,
        )
        session.add(new_cluster)
        await session.flush()
        max_cdf = stats.max_cluster_df or 0
        if max_cdf < count:
            await session.execute(
                update(ThemeStats).where(ThemeStats.id == stats.id).values(max_cluster_df=count)
            )
        await session.flush()
        max_cdf = max(stats.max_cluster_df or 1, count)
        new_score = count / max_cdf
        await session.execute(update(Cluster).where(Cluster.id == new_cluster.id).values(global_score=new_score))

        # cluster_atoms
        for pos, lemma in enumerate(lemmas):
            atom_id = await self._get_or_create_atom(session, theme_id, lemma)
            session.add(
                ClusterAtom(cluster_id=new_cluster.id, atom_id=atom_id, position=pos)
            )
        await session.flush()
        return new_cluster

    async def _recalculate_atom_scores_for_theme(self, session: AsyncSession, theme_id: Any) -> None:
        stats = await self._get_or_create_theme_stats(session, theme_id)
        max_df = stats.max_atom_cluster_df or 1
        result = await session.execute(select(Atom).where(Atom.theme_id == theme_id))
        atoms = list(result.scalars().all())
        for a in atoms:
            spec = a.specificity_score if a.specificity_score is not None else 1.0
            df = a.global_cluster_df or 0
            score = spec * df / max_df
            await session.execute(update(Atom).where(Atom.id == a.id).values(global_score=score))

    async def _recalculate_cluster_scores_for_theme(self, session: AsyncSession, theme_id: Any) -> None:
        stats = await self._get_or_create_theme_stats(session, theme_id)
        max_df = stats.max_cluster_df or 1

        # max specificity_score по атомам в каждом кластере
        res = await session.execute(
            select(
                ClusterAtom.cluster_id,
                func.max(func.coalesce(Atom.specificity_score, 1.0)),
            )
            .join(Atom, Atom.id == ClusterAtom.atom_id)
            .join(Cluster, Cluster.id == ClusterAtom.cluster_id)
            .where(Cluster.theme_id == theme_id)
            .group_by(ClusterAtom.cluster_id)
        )
        max_spec_by_cluster: dict[Any, float] = {cid: float(ms or 1.0) for cid, ms in res.all()}

        result = await session.execute(select(Cluster).where(Cluster.theme_id == theme_id))
        clusters = list(result.scalars().all())
        for c in clusters:
            df = c.global_df or 0
            max_spec = max_spec_by_cluster.get(c.id, 1.0)
            score = (df / max_df) * max_spec
            await session.execute(update(Cluster).where(Cluster.id == c.id).values(global_score=score))
