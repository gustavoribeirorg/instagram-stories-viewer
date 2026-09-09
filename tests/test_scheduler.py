import asyncio
import pytest
from pathlib import Path
from unittest.mock import patch
from services import database, downloader, scheduler
from services.scraper import StoryScraper, BaseStoryProvider, UserProfile, StoryItem

class MockSchedulerProvider(BaseStoryProvider):
    @property
    def name(self) -> str:
        return "MockSchedulerProvider"

    async def fetch_stories(self, username: str) -> UserProfile:
        return UserProfile(
            username=username,
            display_name=f"Full {username}",
            avatar_url="https://example.com/avatar.jpg",
            is_private=False,
            story_count=1,
            stories=[
                StoryItem(
                    story_id=f"story_{username}_1",
                    media_type="image",
                    media_url="https://example.com/pic.jpg",
                    thumbnail_url="https://example.com/pic.jpg"
                )
            ]
        )

@pytest.fixture
def temp_env(tmp_path):
    test_db = tmp_path / "test_stories.db"
    test_downloads = tmp_path / "downloads"
    test_downloads.mkdir()

    database.init_db(test_db)
    orig_db = database.config.DB_PATH
    orig_downloads = downloader.config.DOWNLOADS_DIR
    orig_delay = scheduler.config.REQUEST_DELAY_SECONDS

    database.config.DB_PATH = test_db
    downloader.config.DB_PATH = test_db
    downloader.config.DOWNLOADS_DIR = test_downloads
    scheduler.config.REQUEST_DELAY_SECONDS = 0.01

    yield tmp_path, test_db

    database.config.DB_PATH = orig_db
    downloader.config.DB_PATH = orig_db
    downloader.config.DOWNLOADS_DIR = orig_downloads
    scheduler.config.REQUEST_DELAY_SECONDS = orig_delay

def test_sync_profile_downloads_new_story(temp_env):
    tmp_path, test_db = temp_env
    database.add_monitored_profile("monitored_user")
    
    mock_scraper = StoryScraper(providers=[MockSchedulerProvider()])

    async def mock_download(story, username, **kwargs):
        # Emula download gravando no banco
        database.record_download(story.story_id, username, story.media_type, "path/to/file.jpg")
        return Path("path/to/file.jpg")

    async def run():
        with patch("services.downloader.download_story_media", side_effect=mock_download):
            # 1. Primeira sincronização deve baixar 1 story
            res1 = await scheduler.sync_profile("monitored_user", scraper=mock_scraper)
            assert res1["success"] is True
            assert res1["stories_found"] == 1
            assert res1["stories_downloaded"] == 1

            # 2. Segunda sincronização deve encontrar 1 mas baixar 0 (já gravado)
            res2 = await scheduler.sync_profile("monitored_user", scraper=mock_scraper)
            assert res2["success"] is True
            assert res2["stories_found"] == 1
            assert res2["stories_downloaded"] == 0

    asyncio.run(run())

def test_run_all_monitored_sync(temp_env):
    tmp_path, test_db = temp_env
    database.add_monitored_profile("user_a")
    database.add_monitored_profile("user_b")
    
    mock_scraper = StoryScraper(providers=[MockSchedulerProvider()])

    async def mock_download(story, username, **kwargs):
        database.record_download(story.story_id, username, story.media_type, "path/file.jpg")
        return Path("path/file.jpg")

    async def run():
        with patch("services.downloader.download_story_media", side_effect=mock_download):
            res = await scheduler.run_all_monitored_sync(scraper=mock_scraper)
            assert res["status"] == "completed"
            assert res["profiles_checked"] == 2
            assert res["total_new_downloads"] == 2

    asyncio.run(run())
