"""Seed base event_plots and event_roles

Revision ID: r4s5t6u8v9w0
Revises: q3r4s5t6u8v9
Create Date: 2026-03-06

Создаёт базовые роли и сюжеты событий для MVP-архитектуры.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "r4s5t6u8v9w0"
down_revision: Union[str, Sequence[str], None] = "q3r4s5t6u8v9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Базовые роли участников событий (жёстко зашитые INSERT'ы без параметров)
    op.execute(
        """
        INSERT INTO event_roles (id, code, name, description, created_at)
        VALUES (
            gen_random_uuid(),
            'subject',
            'Субъект',
            'Главный участник события, тот, кто совершает действие или находится в фокусе изменения.',
            now()
        )
        ON CONFLICT (code) DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO event_roles (id, code, name, description, created_at)
        VALUES (
            gen_random_uuid(),
            'object',
            'Объект',
            'То, на что направлено действие или изменение.',
            now()
        )
        ON CONFLICT (code) DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO event_roles (id, code, name, description, created_at)
        VALUES (
            gen_random_uuid(),
            'instrument',
            'Инструмент',
            'Инструмент или средство, с помощью которого совершается действие.',
            now()
        )
        ON CONFLICT (code) DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO event_roles (id, code, name, description, created_at)
        VALUES (
            gen_random_uuid(),
            'reason',
            'Причина',
            'Причина или основание, по которому происходит событие или изменение.',
            now()
        )
        ON CONFLICT (code) DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO event_roles (id, code, name, description, created_at)
        VALUES (
            gen_random_uuid(),
            'speaker',
            'Источник высказывания',
            'Тот, кто делает заявление, выражает позицию или даёт оценку.',
            now()
        )
        ON CONFLICT (code) DO NOTHING;
        """
    )

    # Базовые сюжеты событий
    op.execute(
        """
        INSERT INTO event_plots (id, code, name, description, schema, created_at)
        VALUES (
            gen_random_uuid(),
            'action',
            'Действие',
            'Событие, описывающее действие субъекта в отношении объекта (с возможным инструментом).',
            '{
                "roles": ["subject", "predicate", "object", "instrument"],
                "required_roles": ["subject", "predicate"],
                "attribute_targets": ["subject", "predicate", "object", "instrument", "event"]
            }'::jsonb,
            now()
        )
        ON CONFLICT (code) DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO event_plots (id, code, name, description, schema, created_at)
        VALUES (
            gen_random_uuid(),
            'change',
            'Изменение',
            'Событие, описывающее изменение состояния субъекта, обычно с указанием причины.',
            '{
                "roles": ["subject", "predicate", "reason"],
                "required_roles": ["subject", "predicate"],
                "attribute_targets": ["subject", "predicate", "reason", "event"]
            }'::jsonb,
            now()
        )
        ON CONFLICT (code) DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO event_plots (id, code, name, description, schema, created_at)
        VALUES (
            gen_random_uuid(),
            'relation',
            'Отношение',
            'Событие, фиксирующее устойчивое отношение между субъектом и объектом.',
            '{
                "roles": ["subject", "predicate", "object"],
                "required_roles": ["subject", "predicate", "object"],
                "attribute_targets": ["subject", "predicate", "object", "event"]
            }'::jsonb,
            now()
        )
        ON CONFLICT (code) DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO event_plots (id, code, name, description, schema, created_at)
        VALUES (
            gen_random_uuid(),
            'statement',
            'Высказывание',
            'Событие, где источник высказывания (speaker) делает утверждение об объекте.',
            '{
                "roles": ["speaker", "predicate", "object"],
                "required_roles": ["speaker", "predicate", "object"],
                "attribute_targets": ["speaker", "predicate", "object", "event"]
            }'::jsonb,
            now()
        )
        ON CONFLICT (code) DO NOTHING;
        """
    )


def downgrade() -> None:
    # Удаляем только те записи, которые добавлялись этой миграцией
    op.execute(
        sa.text(
            """
            DELETE FROM event_participants
            WHERE role_id IN (
                SELECT id FROM event_roles WHERE code IN ('subject','object','instrument','reason','speaker')
            )
            """
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM event_roles WHERE code IN ('subject','object','instrument','reason','speaker')"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM event_plots WHERE code IN ('action','change','relation','statement')"
        )
    )

