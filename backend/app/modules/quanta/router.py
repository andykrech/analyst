"""Минимальный API для чтения квантов (без сложной бизнес-логики)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.modules.auth.router import get_current_user
from app.modules.quanta.crud import get_quantum, list_quanta
from app.modules.quanta.models import Quantum
from app.modules.quanta.schemas import (
    QuantumEntitiesOut,
    QuantumEntityOut,
    QuantumListOut,
    QuantumOut,
    QuantumPhenomenonClaimOut,
    QuantumPhenomenonOut,
)
from app.modules.theme.service import get_theme_with_queries
from app.modules.user.model import User
from app.modules.entity.model import Cluster
from app.modules.relation.model import Relation, RelationClaim

router = APIRouter(prefix="/api/v1", tags=["quanta"])


async def _ensure_theme_access(
    db: AsyncSession,
    *,
    theme_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Проверяет, что тема существует и принадлежит пользователю."""
    theme, _ = await get_theme_with_queries(db, theme_id, user_id)
    if not theme:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тема не найдена или недоступна",
        )


def _quantum_row_to_out(q: Quantum) -> QuantumOut:
    return QuantumOut(
        id=str(q.id),
        theme_id=str(q.theme_id),
        run_id=str(q.run_id) if q.run_id else None,
        entity_kind=q.entity_kind.value if hasattr(q.entity_kind, "value") else str(q.entity_kind),
        title=q.title,
        summary_text=q.summary_text,
        key_points=list(q.key_points or []),
        title_translated=q.title_translated,
        summary_text_translated=q.summary_text_translated,
        key_points_translated=list(q.key_points_translated) if q.key_points_translated else None,
        language=q.language,
        date_at=q.date_at,
        verification_url=q.verification_url,
        canonical_url=q.canonical_url,
        dedup_key=q.dedup_key,
        fingerprint=q.fingerprint,
        identifiers=list(q.identifiers or []),
        matched_terms=list(q.matched_terms or []),
        matched_term_ids=list(q.matched_term_ids or []),
        retriever_query=q.retriever_query,
        rank_score=q.rank_score,
        opinion_score=list(q.opinion_score) if q.opinion_score else None,
        total_score=q.total_score,
        source_system=q.source_system,
        site_id=str(q.site_id) if q.site_id else None,
        retriever_name=q.retriever_name,
        retriever_version=q.retriever_version,
        retrieved_at=q.retrieved_at,
        attrs=dict(q.attrs or {}),
        raw_payload_ref=str(q.raw_payload_ref) if q.raw_payload_ref else None,
        content_ref=q.content_ref,
        status=q.status,
        duplicate_of_id=str(q.duplicate_of_id) if q.duplicate_of_id else None,
        created_at=q.created_at,
        updated_at=q.updated_at,
    )


@router.get(
    "/themes/{theme_id}/quanta",
    response_model=QuantumListOut,
)
async def list_theme_quanta_endpoint(
    theme_id: str,
    entity_kind: str | None = Query(None, description="publication|patent|webpage"),
    status_filter: str | None = Query(None, alias="status", description="active|duplicate|rejected|error"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QuantumListOut:
    """Список квантов по теме (с простыми фильтрами)."""
    try:
        tid = uuid.UUID(theme_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат theme_id (ожидается UUID)",
        )

    await _ensure_theme_access(db, theme_id=tid, user_id=current_user.id)
    items, total = await list_quanta(
        db,
        theme_id=tid,
        entity_kind=entity_kind,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return QuantumListOut(items=[_quantum_row_to_out(q) for q in items], total=total)


@router.get(
    "/quanta/{quantum_id}",
    response_model=QuantumOut,
)
async def get_quantum_endpoint(
    quantum_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QuantumOut:
    """Получить квант по id (с проверкой доступа к теме-владельцу)."""
    try:
        qid = uuid.UUID(quantum_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат quantum_id (ожидается UUID)",
        )

    q = await get_quantum(db, quantum_id=qid)
    if not q:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Квант не найден",
        )

    await _ensure_theme_access(db, theme_id=q.theme_id, user_id=current_user.id)
    return _quantum_row_to_out(q)


PHENOMENON_PROPERTY_TYPE = "phenomenon_modifier_condition"


@router.get(
    "/quanta/{quantum_id}/entities",
    response_model=QuantumEntitiesOut,
)
async def get_quantum_entities_endpoint(
    quantum_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QuantumEntitiesOut:
    """Сущности (tech, person, phenomenon) для одного кванта, с модификаторами и условиями для явлений."""
    try:
        qid = uuid.UUID(quantum_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат quantum_id (ожидается UUID)",
        )

    q = await get_quantum(db, quantum_id=qid)
    if not q:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Квант не найден",
        )

    await _ensure_theme_access(db, theme_id=q.theme_id, user_id=current_user.id)

    # Загрузить связи cluster–quantum:
    # - technologies & phenomena: relation_type='mentions'
    # - persons: relation_type='author'
    rel_rows = (
        await db.execute(
            select(Relation, Cluster)
            .join(Cluster, Cluster.id == Relation.subject_id)
            .where(
                Relation.object_type == "quantum",
                Relation.object_id == qid,
                Relation.subject_type == "cluster",
                Relation.relation_type.in_(["mentions", "author"]),
                Relation.deleted_at.is_(None),
                Relation.status == "active",
            )
        )
    ).all()

    relations_by_id: dict[uuid.UUID, Relation] = {}
    tech_entities: list[QuantumEntityOut] = []
    person_entities: list[QuantumEntityOut] = []
    phenomenon_entities_tmp: list[tuple[uuid.UUID, QuantumPhenomenonOut]] = []

    for rel, cluster in rel_rows:
        rel_id = rel.id
        relations_by_id[rel_id] = rel

        base = QuantumEntityOut(
            id=str(cluster.id),
            entity_type=cluster.type,
            normalized_name=cluster.normalized_text,
            canonical_name=cluster.display_text,
        )

        if cluster.type == "tech" and rel.relation_type == "mentions":
            tech_entities.append(base)
        elif cluster.type == "person" and rel.relation_type == "author":
            person_entities.append(base)
        elif cluster.type == "phenomenon" and rel.relation_type == "mentions":
            phenomenon_entities_tmp.append(
                (
                    rel_id,
                    QuantumPhenomenonOut(
                        id=base.id,
                        entity_type=base.entity_type,
                        normalized_name=base.normalized_name,
                        canonical_name=base.canonical_name,
                        claims=[],
                    ),
                )
            )

    # Загрузить claims только для связей явлений
    phenomenon_rel_ids = [rel_id for rel_id, _ in phenomenon_entities_tmp]
    claims_by_relation: dict[uuid.UUID, list[QuantumPhenomenonClaimOut]] = {}
    if phenomenon_rel_ids:
        claim_rows = (
            await db.execute(
                select(RelationClaim).where(
                    RelationClaim.relation_id.in_(phenomenon_rel_ids),
                    RelationClaim.property_type == PHENOMENON_PROPERTY_TYPE,
                )
            )
        ).scalars().all()

        for c in claim_rows:
            props = c.properties_json or {}
            mod = str(props.get("modifier") or "").strip()
            cond = str(props.get("condition_text") or "").strip()
            claims_by_relation.setdefault(c.relation_id, []).append(
                QuantumPhenomenonClaimOut(modifier=mod, condition_text=cond)
            )

    phenomena: list[QuantumPhenomenonOut] = []
    for rel_id, phen in phenomenon_entities_tmp:
        phen.claims = claims_by_relation.get(rel_id, []) or [
            QuantumPhenomenonClaimOut(modifier="", condition_text="")
        ]
        phenomena.append(phen)

    return QuantumEntitiesOut(
        tech=tech_entities,
        persons=person_entities,
        phenomena=phenomena,
    )

