"""widen job labor_cost and tenant default_tax_rate to double precision

Revision ID: c689748f0026
Revises: ccd329b22956
Create Date: 2026-08-15 10:15:25.908575

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c689748f0026'
down_revision = 'ccd329b22956'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # batch_alter_table, not alter_column: SQLite has no ALTER COLUMN, so it
    # recreates the table instead. MySQL still gets a plain ALTER.
    with op.batch_alter_table('jobs') as batch_op:
        batch_op.alter_column(
            'labor_cost', existing_type=sa.Float(), type_=sa.Float(precision=53), nullable=False
        )
    with op.batch_alter_table('tenants') as batch_op:
        batch_op.alter_column(
            'default_tax_rate', existing_type=sa.Float(), type_=sa.Float(precision=53), nullable=False
        )


def downgrade() -> None:
    with op.batch_alter_table('tenants') as batch_op:
        batch_op.alter_column(
            'default_tax_rate', existing_type=sa.Float(precision=53), type_=sa.Float(), nullable=False
        )
    with op.batch_alter_table('jobs') as batch_op:
        batch_op.alter_column(
            'labor_cost', existing_type=sa.Float(precision=53), type_=sa.Float(), nullable=False
        )
