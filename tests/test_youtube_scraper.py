import sys
import unittest
from unittest.mock import MagicMock, patch


class TestYoutubeScraper(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.mock_modules = {
            'backend': MagicMock(),
            'backend.models': MagicMock(),
            'backend.database': MagicMock(),
            'isodate': MagicMock(),
            'dotenv': MagicMock(),
            'httpx': MagicMock(),
            'sqlalchemy': MagicMock(),
            'sqlalchemy.dialects': MagicMock(),
            'sqlalchemy.dialects.postgresql': MagicMock(),
        }
        cls.patcher = patch.dict(sys.modules, cls.mock_modules)
        cls.patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls.patcher.stop()

    async def test_insert_video_success(self):
        import scraper.youtube_scraper as ys
        video = {
            'id': 'test_id',
            'snippet': {
                'title': 'Test Title',
                'description': 'Test Description',
                'thumbnails': {'high': {'url': 'test_url'}},
                'publishedAt': '2023-01-01'
            },
            'contentDetails': {'duration': 'PT10M'},
            'statistics': {'viewCount': '100', 'likeCount': '10'}
        }

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1

        async def mock_execute(*args, **kwargs):
            return mock_result

        mock_session.execute = mock_execute

        async def mock_commit(): pass
        async def mock_close(): pass

        mock_session.commit = mock_commit
        mock_session.close = mock_close

        result = await ys.insert_video(video, db_session=mock_session)
        self.assertTrue(result)

    async def test_insert_video_duplicate(self):
        import scraper.youtube_scraper as ys
        video = {
            'id': 'test_id',
            'snippet': {
                'title': 'Test Title',
                'description': 'Test Description',
                'thumbnails': {'high': {'url': 'test_url'}},
                'publishedAt': '2023-01-01'
            },
            'contentDetails': {'duration': 'PT10M'},
            'statistics': {'viewCount': '100', 'likeCount': '10'}
        }

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 0

        async def mock_execute(*args, **kwargs):
            return mock_result

        mock_session.execute = mock_execute

        async def mock_commit(): pass
        async def mock_close(): pass

        mock_session.commit = mock_commit
        mock_session.close = mock_close

        result = await ys.insert_video(video, db_session=mock_session)
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()
