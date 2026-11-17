"""Live Activity tokens for iPhones

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("devices") as batch_op:
        batch_op.add_column(sa.Column("live_activity_start_token", sa.String(length=256), nullable=True))
    with op.batch_alter_table("calls") as batch_op:
        batch_op.add_column(sa.Column("live_activity_token", sa.String(length=256), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("calls") as batch_op:
        batch_op.drop_column("live_activity_token")
    with op.batch_alter_table("devices") as batch_op:
        batch_op.drop_column("live_activity_start_token")
