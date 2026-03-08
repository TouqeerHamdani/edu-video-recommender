"""Add HNSW vector index to videos.embedding

Revision ID: b3d9f1a72e04
Revises: a7495d878893
Create Date: 2026-03-07 00:00:00.000000

Adds an HNSW (Hierarchical Navigable Small World) index on the embedding column
of the videos table using cosine distance ops. This replaces the O(N) exact
nearest-neighbour scan with an approximate O(log N) search, drastically
reducing latency for vector similarity queries via pgvector.

Index parameters:
  m=16             — number of bi-directional links per node (quality/memory trade-off)
  ef_construction=64 — size of the dynamic candidate list during index build
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b3d9f1a72e04'
down_revision: Union[str, None] = 'a7495d878893'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_video_embedding_hnsw
        ON public.videos
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.ix_video_embedding_hnsw;")
