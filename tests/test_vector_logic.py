"""
Tests for scraper/semantic_search.py — vector search and FTS logic.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np

from scraper.semantic_search import create_query_embedding, recommend


class TestCreateQueryEmbedding:
    """Tests for create_query_embedding()."""

    def test_returns_none_when_credentials_missing(self):
        """Returns None when Cloudflare credentials are not configured."""
        with patch("scraper.semantic_search.CLOUDFLARE_ACCOUNT_ID", ""), \
             patch("scraper.semantic_search.CLOUDFLARE_API_TOKEN", ""):
            result = asyncio.run(create_query_embedding("test query"))
        assert result is None

    def test_returns_cached_result(self):
        """Uses the in-process cache to avoid repeated Cloudflare API calls."""
        cached_vec = [0.1] * 384
        with patch.dict("scraper.semantic_search._embedding_cache", {"cached query": cached_vec}):
            result = asyncio.run(create_query_embedding("cached query"))
        assert result is not None
        assert len(result) == 384


class TestRecommend:
    """Tests for recommend() — FTS fallback and vector search paths."""

    def _make_session(self):
        """Return an AsyncMock session whose execute() captures SQL strings."""
        session = AsyncMock()
        self._executed_sqls = []

        async def capture(sql, params=None):
            self._executed_sqls.append(str(sql))
            result = MagicMock()
            result.scalars.return_value.first.return_value = None
            result.fetchall.return_value = []
            result.__iter__ = MagicMock(return_value=iter([]))
            return result

        session.execute.side_effect = capture
        return session

    def test_uses_fts_when_no_embeddings_in_db(self):
        """recommend() issues a websearch_to_tsquery FTS query when no embeddings exist."""
        session = self._make_session()

        with patch("scraper.semantic_search._check_has_embeddings", new=AsyncMock(return_value=False)), \
             patch("scraper.semantic_search.create_query_embedding", new=AsyncMock(return_value=None)), \
             patch("scraper.youtube_scraper.fetch_and_store_videos", new=AsyncMock(return_value=0)):
            asyncio.run(recommend("python tutorial", top_n=5, db_session=session))

        assert any("websearch_to_tsquery" in sql for sql in self._executed_sqls), (
            f"Expected FTS SQL (websearch_to_tsquery) but executed: {self._executed_sqls}"
        )

    def test_uses_vector_search_when_embeddings_exist(self):
        """recommend() issues a <=> pgvector query when embeddings are present."""
        session = self._make_session()
        fake_embedding = np.array([0.1] * 384, dtype="float32")

        with patch("scraper.semantic_search._check_has_embeddings", new=AsyncMock(return_value=True)), \
             patch("scraper.semantic_search.create_query_embedding", new=AsyncMock(return_value=fake_embedding)), \
             patch("scraper.youtube_scraper.fetch_and_store_videos", new=AsyncMock(return_value=0)):
            asyncio.run(recommend("python tutorial", top_n=5, db_session=session))

        assert any("<=>" in sql for sql in self._executed_sqls), (
            f"Expected vector SQL (<=>) but executed: {self._executed_sqls}"
        )
