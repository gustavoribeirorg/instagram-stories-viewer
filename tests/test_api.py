import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app import app
from services import database
from services.scraper import UserProfile, StoryItem

@pytest.fixture
def client_env(tmp_path):
    test_db = tmp_path / "test_api_stories.db"
    test_downloads = tmp_path / "downloads"
    test_downloads.mkdir()

    database.init_db(test_db)
    orig_db = database.config.DB_PATH
    database.config.DB_PATH = test_db

    with TestClient(app) as c:
        yield c, test_db

    database.config.DB_PATH = orig_db

def test_home_page(client_env):
    client, _ = client_env
    response = client.get("/")
    assert response.status_code == 200
    assert "Stories Viewer & Downloader" in response.text

def test_monitored_crud(client_env):
    client, _ = client_env
    # 1. Add monitored
    post_res = client.post("/api/monitored", json={"username": "api_test_user", "display_name": "API Tester"})
    assert post_res.status_code == 200
    assert post_res.json()["username"] == "api_test_user"

    # 2. List
    list_res = client.get("/api/monitored")
    assert list_res.status_code == 200
    profiles = list_res.json()
    assert any(p["username"] == "api_test_user" for p in profiles)

    # 3. Toggle
    patch_res = client.patch("/api/monitored/api_test_user", json={"is_active": False})
    assert patch_res.status_code == 200

    # 4. Delete
    del_res = client.delete("/api/monitored/api_test_user")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] == "api_test_user"

def test_get_stories_mock(client_env):
    client, _ = client_env
    mock_profile = UserProfile(
        username="famous_user",
        display_name="Famous Star",
        avatar_url="https://example.com/avatar.jpg",
        is_private=False,
        story_count=1,
        stories=[
            StoryItem(
                story_id="story_999",
                media_type="image",
                media_url="https://example.com/story.jpg",
                thumbnail_url="https://example.com/story.jpg"
            )
        ]
    )

    with patch("app.scraper.get_stories", new=AsyncMock(return_value=mock_profile)):
        res = client.get("/api/stories/famous_user")
        assert res.status_code == 200
        data = res.json()
        assert data["username"] == "famous_user"
        assert len(data["stories"]) == 1
        assert data["stories"][0]["story_id"] == "story_999"

def test_get_stats(client_env):
    client, _ = client_env
    res = client.get("/api/stats")
    assert res.status_code == 200
    data = res.json()
    assert "total_monitored" in data
    assert "total_downloads" in data
    assert "scheduler" in data
