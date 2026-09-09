import asyncio
import pytest
from services.scraper import (
    BaseStoryProvider,
    StoryScraper,
    UserProfile,
    StoryItem,
    ProfileNotFoundError,
    ProfilePrivateError,
    ScraperException,
)

class MockFailingProvider(BaseStoryProvider):
    @property
    def name(self) -> str:
        return "FailingProvider"

    async def fetch_stories(self, username: str) -> UserProfile:
        raise ScraperException("Network timeout simulation")

class MockSuccessProvider(BaseStoryProvider):
    @property
    def name(self) -> str:
        return "SuccessProvider"

    async def fetch_stories(self, username: str) -> UserProfile:
        return UserProfile(
            username=username,
            display_name="Mock Full Name",
            avatar_url="https://example.com/avatar.jpg",
            is_private=False,
            story_count=2,
            stories=[
                StoryItem(
                    story_id="s_1",
                    media_type="image",
                    media_url="https://example.com/s1.jpg",
                    thumbnail_url="https://example.com/s1_thumb.jpg",
                ),
                StoryItem(
                    story_id="s_2",
                    media_type="video",
                    media_url="https://example.com/s2.mp4",
                    thumbnail_url="https://example.com/s2_thumb.jpg",
                ),
            ],
        )

class MockPrivateProvider(BaseStoryProvider):
    @property
    def name(self) -> str:
        return "PrivateProvider"

    async def fetch_stories(self, username: str) -> UserProfile:
        raise ProfilePrivateError("privado")

def test_scraper_fallback_to_second_provider():
    async def run():
        scraper = StoryScraper(providers=[MockFailingProvider(), MockSuccessProvider()])
        result = await scraper.get_stories("test_user")
        assert result.username == "test_user"
        assert result.story_count == 2
        assert result.stories[0].media_type == "image"
        assert result.stories[1].media_type == "video"
    asyncio.run(run())

def test_scraper_detects_private_profile():
    async def run():
        scraper = StoryScraper(providers=[MockPrivateProvider()])
        with pytest.raises(ProfilePrivateError):
            await scraper.get_stories("private_user")
    asyncio.run(run())

def test_scraper_all_fail():
    async def run():
        scraper = StoryScraper(providers=[MockFailingProvider()])
        with pytest.raises(ScraperException) as excinfo:
            await scraper.get_stories("any_user")
        assert "Detalhes" in str(excinfo.value)
    asyncio.run(run())

def test_scraper_invalid_username():
    async def run():
        scraper = StoryScraper(providers=[MockSuccessProvider()])
        with pytest.raises(ScraperException) as excinfo:
            await scraper.get_stories("user with spaces!#$")
        assert "user with spaces!#$" in str(excinfo.value)
    asyncio.run(run())

