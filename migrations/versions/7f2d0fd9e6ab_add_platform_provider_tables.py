"""add_platform_provider_tables

Revision ID: 7f2d0fd9e6ab
Revises: 0043323f6947
Create Date: 2026-06-25 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7f2d0fd9e6ab"
down_revision: Union[str, Sequence[str], None] = "0043323f6947"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "core_provider_configs",
        sa.Column("provider_type", sa.String(length=50), nullable=False),
        sa.Column("provider_name", sa.String(length=100), nullable=False),
        sa.Column("environment", sa.String(length=50), nullable=False),
        sa.Column("encrypted_credentials", sa.String(length=10000), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("supported_countries", sa.JSON(), nullable=False),
        sa.Column("supported_currencies", sa.JSON(), nullable=False),
        sa.Column("last_test_status", sa.String(length=50), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column("updated_by_user_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["platform_admins.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["platform_admins.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_core_provider_configs_provider_type", "core_provider_configs", ["provider_type"], unique=False)
    op.create_index("ix_core_provider_configs_is_active", "core_provider_configs", ["is_active"], unique=False)
    op.create_index("ix_core_provider_configs_is_default", "core_provider_configs", ["is_default"], unique=False)

    op.create_table(
        "core_provider_logs",
        sa.Column("provider_config_id", sa.UUID(), nullable=False),
        sa.Column("provider_type", sa.String(length=50), nullable=False),
        sa.Column("provider_name", sa.String(length=100), nullable=False),
        sa.Column("operation", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("request_payload_masked", sa.JSON(), nullable=False),
        sa.Column("response_payload_masked", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["provider_config_id"], ["core_provider_configs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_core_provider_logs_provider_config_id", "core_provider_logs", ["provider_config_id"], unique=False)
    op.create_index("ix_core_provider_logs_created_at", "core_provider_logs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_core_provider_logs_created_at", table_name="core_provider_logs")
    op.drop_index("ix_core_provider_logs_provider_config_id", table_name="core_provider_logs")
    op.drop_table("core_provider_logs")

    op.drop_index("ix_core_provider_configs_is_default", table_name="core_provider_configs")
    op.drop_index("ix_core_provider_configs_is_active", table_name="core_provider_configs")
    op.drop_index("ix_core_provider_configs_provider_type", table_name="core_provider_configs")
    op.drop_table("core_provider_configs")
