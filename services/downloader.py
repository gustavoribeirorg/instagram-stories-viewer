import os
import re
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import httpx
import config
from services import database
from services.scraper import StoryItem

logger = logging.getLogger(__name__)

async def download_story_media(
    story: StoryItem,
    username: str,
    skip_if_exists: bool = True
) -> Optional[Path]:
    clean_username = username.strip().lower().lstrip("@")
    
    if skip_if_exists and database.is_story_downloaded(story.story_id):
        logger.info(f"Story {story.story_id} de @{clean_username} ja foi baixado anteriormente. Pulando.")
        return None

    user_dir = config.DOWNLOADS_DIR / clean_username
    user_dir.mkdir(parents=True, exist_ok=True)

    # Determine extension
    ext = ".mp4" if story.media_type == "video" else ".jpg"

    # Format timestamp for filename
    time_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    if story.posted_at:
        try:
            dt = datetime.fromisoformat(story.posted_at)
            time_prefix = dt.strftime("%Y-%m-%d_%H-%M-%S")
        except Exception:
            pass

    clean_story_id = re.sub(r"[^a-zA-Z0-9_-]", "_", story.story_id)
    filename = f"{time_prefix}_{clean_story_id}{ext}"
    target_path = user_dir / filename
    temp_path = user_dir / f"{filename}.tmp"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Referer": "https://www.instagram.com/",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            async with client.stream("GET", story.media_url, headers=headers) as response:
                if response.status_code != 200:
                    logger.error(f"Falha ao baixar mídia {story.media_url}: status {response.status_code}")
                    return None
                
                with open(temp_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=65536):
                        f.write(chunk)

        # Atomic rename
        if temp_path.exists():
            temp_path.replace(target_path)

        relative_path = target_path.relative_to(config.BASE_DIR).as_posix()
        database.record_download(
            story_id=story.story_id,
            username=clean_username,
            media_type=story.media_type,
            file_path=relative_path,
            posted_at=story.posted_at
        )

        logger.info(f"Story {story.story_id} baixado com sucesso em {relative_path}")
        return target_path

    except Exception as e:
        logger.error(f"Erro ao baixar story {story.story_id}: {e}")
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
        return None

def list_downloaded_files(username: Optional[str] = None) -> List[Dict[str, Any]]:
    results = []
    base_downloads = config.DOWNLOADS_DIR
    if not base_downloads.exists():
        return results

    if username:
        user_dirs = [base_downloads / username.strip().lower().lstrip("@")]
    else:
        user_dirs = [d for d in base_downloads.iterdir() if d.is_dir()]

    for user_dir in user_dirs:
        if not user_dir.exists():
            continue
        user = user_dir.name
        for file in user_dir.iterdir():
            if file.is_file() and not file.name.endswith(".tmp"):
                ext = file.suffix.lower()
                media_type = "video" if ext in [".mp4", ".mov", ".webm"] else "image"
                stat = file.stat()
                results.append({
                    "username": user,
                    "filename": file.name,
                    "file_path": file.relative_to(config.BASE_DIR).as_posix(),
                    "web_url": f"/downloads/{user}/{file.name}",
                    "media_type": media_type,
                    "size_bytes": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_ctime, timezone.utc).isoformat()
                })

    # Sort newest first
    results.sort(key=lambda x: x["created_at"], reverse=True)
    return results
