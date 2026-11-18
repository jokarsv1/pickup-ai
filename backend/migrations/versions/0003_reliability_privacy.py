"""Missed-forwarding detection, contacts stay on the phone, TRAI series settings, support reports

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("lines") as batch_op:
        batch_op.add_column(sa.Column("missed_streak", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("forwarding_alert_at", sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table("assistant_settings") as batch_op:
        batch_op.add_column(sa.Column("ring_verified_business", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column("ring_repeat_callers", sa.Boolean(), nullable=False, server_default=sa.true()))
    with op.batch_alter_table("screening_hints") as batch_op:
        batch_op.add_column(sa.Column("caller_name", sa.String(length=120), nullable=True))
    op.create_table(
        "support_reports",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("user_id", sa.String(length=40), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("diagnostics", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_support_reports_user_id", "support_reports", ["user_id"])
    op.create_index("ix_support_reports_created_at", "support_reports", ["created_at"])
    # Address books no longer leave the phone: delete what earlier app versions uploaded.
    op.execute("DELETE FROM contacts")


def downgrade() -> None:
    op.drop_index("ix_support_reports_created_at", table_name="support_reports")
    op.drop_index("ix_support_reports_user_id", table_name="support_reports")
    op.drop_table("support_reports")
    with op.batch_alter_table("screening_hints") as batch_op:
        batch_op.drop_column("caller_name")
    with op.batch_alter_table("assistant_settings") as batch_op:
        batch_op.drop_column("ring_repeat_callers")
        batch_op.drop_column("ring_verified_business")
    with op.batch_alter_table("lines") as batch_op:
        batch_op.drop_column("forwarding_alert_at")
        batch_op.drop_column("missed_streak")
