"""Add GIN full-text search index to videos

Revision ID: c5e2a0b81f19
Revises: b3d9f1a72e04
Create Date: 2026-03-07 00:01:00.000000

Adds a GIN expression index on to_tsvector('english', title || description)
for the videos table. Replaces O(N) ILIKE full table scans with instantaneous
full-text index lookups via to_tsvector / websearch_to_tsquery.

No schema change — expression index only.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c5e2a0b81f19'
down_revision: Union[str, None] = 'b3d9f1a72e04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_videos_fts
        ON public.videos
        USING gin(to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, '')));
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.ix_videos_fts;")
