import asyncio
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from services import database, downloader
from services.scraper import StoryItem

@pytest.fixture
def temp_env(tmp_path):
    # Setup test db and download dir
    test_db = tmp_path / "test_stories.db"
    test_downloads = tmp_path / "downloads"
    test_downloads.mkdir()

    database.init_db(test_db)
    orig_db = database.config.DB_PATH
    orig_downloads = downloader.config.DOWNLOADS_DIR
    orig_base = downloader.config.BASE_DIR

    database.config.DB_PATH = test_db
    downloader.config.DB_PATH = test_db
    downloader.config.DOWNLOADS_DIR = test_downloads
    downloader.config.BASE_DIR = tmp_path

    yield tmp_path, test_downloads

    database.config.DB_PATH = orig_db
    downloader.config.DB_PATH = orig_db
    downloader.config.DOWNLOADS_DIR = orig_downloads
    downloader.config.BASE_DIR = orig_base

def test_download_story_media_and_skip_duplicate(temp_env):
    tmp_path, downloads_dir = temp_env

    story = StoryItem(
        story_id="mock_story_101",
        media_type="image",
        media_url="https://example.com/fake_image.jpg",
        thumbnail_url="https://example.com/fake_thumb.jpg",
        posted_at="2026-09-08T12:00:00+00:00"
    )

    # Mock httpx streaming response
    class FakeStream:
        def __init__(self):
            self.status_code = 200
        async def aiter_bytes(self, chunk_size=65536):
            yield b"FAKE_IMAGE_DATA_BYTES"
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass

    class FakeClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        def stream(self, method, url, **kwargs):
            return FakeStream()

    async def run():
        with patch("httpx.AsyncClient", return_value=FakeClient()):
            # 1. First download should succeed
            path = await downloader.download_story_media(story, "test_user")
            assert path is not None
            assert path.exists()
            assert path.read_bytes() == b"FAKE_IMAGE_DATA_BYTES"
            assert database.is_story_downloaded("mock_story_101")

            # 2. Second download should skip due to duplicate check
            second_path = await downloader.download_story_media(story, "test_user")
            assert second_path is None

            # 3. Check list_downloaded_files
            files = downloader.list_downloaded_files("test_user")
            assert len(files) == 1
            assert files[0]["username"] == "test_user"
            assert files[0]["media_type"] == "image"

    asyncio.run(run())
