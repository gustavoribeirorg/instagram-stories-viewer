import sqlite3
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pathlib import Path
import config

def get_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    target_path = db_path or config.DB_PATH
    conn = sqlite3.connect(str(target_path))
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: Optional[Path] = None) -> None:
    conn = get_connection(db_path)
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS monitored_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                display_name TEXT,
                avatar_url TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_checked_at TIMESTAMP
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS downloaded_stories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                story_id TEXT UNIQUE NOT NULL,
                username TEXT NOT NULL,
                media_type TEXT NOT NULL,
                file_path TEXT NOT NULL,
                posted_at TIMESTAMP,
                downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_downloaded_username 
            ON downloaded_stories(username);
        """)
    conn.close()

def add_monitored_profile(
    username: str, 
    display_name: str = "", 
    avatar_url: str = ""
) -> bool:
    clean_username = username.strip().lower().lstrip("@")
    conn = get_connection()
    try:
        with conn:
            conn.execute("""
                INSERT INTO monitored_profiles (username, display_name, avatar_url, is_active)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(username) DO UPDATE SET
                    display_name = COALESCE(NULLIF(excluded.display_name, ''), monitored_profiles.display_name),
                    avatar_url = COALESCE(NULLIF(excluded.avatar_url, ''), monitored_profiles.avatar_url),
                    is_active = 1;
            """, (clean_username, display_name, avatar_url))
        return True
    finally:
        conn.close()

def get_monitored_profiles(active_only: bool = False) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = "SELECT * FROM monitored_profiles"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY username ASC"
        cursor.execute(query)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def toggle_profile_active(username: str, is_active: bool) -> bool:
    clean_username = username.strip().lower().lstrip("@")
    conn = get_connection()
    try:
        with conn:
            cursor = conn.execute("""
                UPDATE monitored_profiles
                SET is_active = ?
                WHERE username = ?;
            """, (1 if is_active else 0, clean_username))
            return cursor.rowcount > 0
    finally:
        conn.close()

def delete_monitored_profile(username: str) -> bool:
    clean_username = username.strip().lower().lstrip("@")
    conn = get_connection()
    try:
        with conn:
            cursor = conn.execute("""
                DELETE FROM monitored_profiles
                WHERE username = ?;
            """, (clean_username,))
            return cursor.rowcount > 0
    finally:
        conn.close()

def update_last_checked(username: str) -> None:
    clean_username = username.strip().lower().lstrip("@")
    conn = get_connection()
    try:
        with conn:
            conn.execute("""
                UPDATE monitored_profiles
                SET last_checked_at = ?
                WHERE username = ?;
            """, (get_utc_now(), clean_username))
    finally:
        conn.close()

def is_story_downloaded(story_id: str) -> bool:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM downloaded_stories WHERE story_id = ? LIMIT 1;", (str(story_id),))
        return cursor.fetchone() is not None
    finally:
        conn.close()

def record_download(
    story_id: str,
    username: str,
    media_type: str,
    file_path: str,
    posted_at: Optional[str] = None
) -> bool:
    clean_username = username.strip().lower().lstrip("@")
    conn = get_connection()
    try:
        with conn:
            conn.execute("""
                INSERT OR IGNORE INTO downloaded_stories 
                (story_id, username, media_type, file_path, posted_at, downloaded_at)
                VALUES (?, ?, ?, ?, ?, ?);
            """, (
                str(story_id), 
                clean_username, 
                media_type, 
                file_path, 
                posted_at, 
                get_utc_now()
            ))
        return True
    except Exception:
        return False
    finally:
        conn.close()

def get_download_history(
    username: Optional[str] = None, 
    limit: int = 50
) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if username:
            clean_username = username.strip().lower().lstrip("@")
            cursor.execute("""
                SELECT * FROM downloaded_stories
                WHERE username = ?
                ORDER BY downloaded_at DESC
                LIMIT ?;
            """, (clean_username, limit))
        else:
            cursor.execute("""
                SELECT * FROM downloaded_stories
                ORDER BY downloaded_at DESC
                LIMIT ?;
            """, (limit,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def get_stats() -> Dict[str, Any]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total_monitored FROM monitored_profiles WHERE is_active = 1;")
        total_monitored = cursor.fetchone()["total_monitored"]
        
        cursor.execute("SELECT COUNT(*) as total_downloads FROM downloaded_stories;")
        total_downloads = cursor.fetchone()["total_downloads"]
        
        return {
            "total_monitored": total_monitored,
            "total_downloads": total_downloads
        }
    finally:
        conn.close()
