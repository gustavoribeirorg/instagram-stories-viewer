import pytest
import sqlite3
from pathlib import Path
from services import database

@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_stories.db"
    database.init_db(db_file)
    # Monkeypatch config.DB_PATH for tests
    original_db = database.config.DB_PATH
    database.config.DB_PATH = db_file
    yield db_file
    database.config.DB_PATH = original_db

def test_init_db(temp_db):
    assert temp_db.exists()
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row["name"] for row in cursor.fetchall()]
    assert "monitored_profiles" in tables
    assert "downloaded_stories" in tables
    conn.close()

def test_add_and_list_monitored_profile(temp_db):
    assert database.add_monitored_profile("test_user", "Test User", "https://avatar.png")
    profiles = database.get_monitored_profiles()
    assert len(profiles) == 1
    assert profiles[0]["username"] == "test_user"
    assert profiles[0]["display_name"] == "Test User"
    assert profiles[0]["is_active"] == 1

def test_toggle_and_delete_profile(temp_db):
    database.add_monitored_profile("sample_profile")
    
    # Toggle active
    assert database.toggle_profile_active("sample_profile", False)
    active = database.get_monitored_profiles(active_only=True)
    assert len(active) == 0
    all_profiles = database.get_monitored_profiles(active_only=False)
    assert len(all_profiles) == 1
    
    # Delete
    assert database.delete_monitored_profile("sample_profile")
    assert len(database.get_monitored_profiles()) == 0

def test_record_and_check_duplicate_download(temp_db):
    story_id = "story_12345"
    assert not database.is_story_downloaded(story_id)
    
    assert database.record_download(
        story_id=story_id,
        username="sample_user",
        media_type="video",
        file_path="downloads/sample_user/2026-09-08_video.mp4"
    )
    
    # Now it should report as downloaded
    assert database.is_story_downloaded(story_id)
    
    # Duplicate insert should be ignored without exception
    assert database.record_download(
        story_id=story_id,
        username="sample_user",
        media_type="video",
        file_path="downloads/sample_user/duplicate.mp4"
    )
    
    history = database.get_download_history("sample_user")
    assert len(history) == 1
