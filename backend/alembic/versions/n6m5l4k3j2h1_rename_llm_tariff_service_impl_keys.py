"""LLM тарифы: service_impl deepseek_in/out → deepseek_deepseek_chat_in/out.

Revision ID: n6m5l4k3j2h1
Revises: k7m8n9o0p1q2
Create Date: 2026-03-22

Соглашение: {provider}_{model}_{in|out} (модель из конфига deepseek-chat → deepseek_chat).
"""

from typing import Sequence, Union

from alembic import op

revision: str = "n6m5l4k3j2h1"
down_revision: Union[str, Sequence[str], None] = "k7m8n9o0p1q2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE billing_tariffs
        SET service_impl = 'deepseek_deepseek_chat_in'
        WHERE service_type = 'llm'
          AND service_impl = 'deepseek_in'
          AND unit_code = 'input_tokens'
        """
    )
    op.execute(
        """
        UPDATE billing_tariffs
        SET service_impl = 'deepseek_deepseek_chat_out'
        WHERE service_type = 'llm'
          AND service_impl = 'deepseek_out'
          AND unit_code = 'output_tokens'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE billing_tariffs
        SET service_impl = 'deepseek_in'
        WHERE service_type = 'llm'
          AND service_impl = 'deepseek_deepseek_chat_in'
          AND unit_code = 'input_tokens'
        """
    )
    op.execute(
        """
        UPDATE billing_tariffs
        SET service_impl = 'deepseek_out'
        WHERE service_type = 'llm'
          AND service_impl = 'deepseek_deepseek_chat_out'
          AND unit_code = 'output_tokens'
        """
    )
