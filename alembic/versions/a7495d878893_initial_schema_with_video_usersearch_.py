"""Initial schema with Video UserSearch UserInteraction

Revision ID: a7495d878893
Revises: 
Create Date: 2026-02-07 07:22:51.585898

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7495d878893'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Schema already exists in Supabase - this is a baseline migration.
    # Tables: videos, user_searches, user_interactions
    # auth.users is managed by Supabase Auth, not Alembic.
    pass


def downgrade() -> None:
    # No-op: Cannot downgrade from initial baseline
    pass

