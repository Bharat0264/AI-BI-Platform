"""initial AURA-BI persistence schema

Revision ID: 20260825_01
Revises:
"""
from alembic import op
from persistence.database import Base
import persistence.models  # noqa: F401
revision = "20260825_01"
down_revision = None
branch_labels = None
depends_on = None
def upgrade():
    Base.metadata.create_all(bind=op.get_bind())
def downgrade():
    Base.metadata.drop_all(bind=op.get_bind())
