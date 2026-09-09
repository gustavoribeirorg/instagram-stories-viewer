import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, Dict, Any, List

import httpx
from fastapi import FastAPI, HTTPException, Query, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import config
from services import database, downloader, scheduler
from services.scraper import (
    StoryScraper,
    StoryItem,
    ProfileNotFoundError,
    ProfilePrivateError,
    ScraperException,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("stories_app")

scraper = StoryScraper()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando Stories App...")
    database.init_db()
    scheduler.start_scheduler()
    yield
    logger.info("Encerrando Stories App...")
    scheduler.stop_scheduler()

app = FastAPI(
    title="Instagram Stories Viewer & Auto-Downloader",
    description="Aplicativo autônomo para visualização e download diário de stories públicos sem login.",
    version="1.0.0",
    lifespan=lifespan
)

# Servir arquivos estáticos e de downloads
app.mount("/static", StaticFiles(directory=str(config.BASE_DIR / "static")), name="static")
app.mount("/downloads", StaticFiles(directory=str(config.DOWNLOADS_DIR)), name="downloads")

templates = Jinja2Templates(directory=str(config.BASE_DIR / "templates"))

# --- Modelos de Entrada ---
class AddProfileRequest(BaseModel):
    username: str
    display_name: Optional[str] = ""
    avatar_url: Optional[str] = ""

class ToggleActiveRequest(BaseModel):
    is_active: bool

class DownloadSingleRequest(BaseModel):
    username: str
    story: StoryItem

# --- Rotas Principais ---

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/api/stories/{username}")
async def get_stories(username: str):
    clean_user = username.strip().lower().lstrip("@")
    try:
        profile = await scraper.get_stories(clean_user)
        return profile.model_dump()
    except ProfileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ProfilePrivateError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ScraperException as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Erro inesperado ao consultar @{clean_user}: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao processar stories.")

@app.get("/api/proxy-media")
async def proxy_media(url: str = Query(..., description="URL original da CDN")):
    if not url.startswith("http://") and not url.startswith("https://"):
        raise HTTPException(status_code=400, detail="URL inválida.")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Referer": "https://www.instagram.com/",
    }

    client = httpx.AsyncClient(timeout=20.0, follow_redirects=True)
    try:
        req = client.build_request("GET", url, headers=headers)
        res = await client.send(req, stream=True)

        if res.status_code != 200:
            await client.aclose()
            raise HTTPException(status_code=res.status_code, detail="Falha ao carregar mídia na CDN.")

        content_type = res.headers.get("content-type", "application/octet-stream")

        async def stream_content():
            try:
                async for chunk in res.aiter_bytes(chunk_size=65536):
                    yield chunk
            finally:
                await res.aclose()
                await client.aclose()

        return StreamingResponse(
            stream_content(),
            media_type=content_type,
            headers={
                "Cache-Control": "public, max-age=86400",
                "Access-Control-Allow-Origin": "*"
            }
        )
    except Exception as e:
        await client.aclose()
        logger.error(f"Erro no proxy de mídia: {e}")
        raise HTTPException(status_code=502, detail=f"Erro ao transmitir mídia: {e}")

# --- Rotas de Perfis Monitorados & Automação ---

@app.get("/api/monitored")
async def list_monitored(active_only: bool = False):
    return database.get_monitored_profiles(active_only=active_only)

@app.post("/api/monitored")
async def add_monitored(data: AddProfileRequest):
    success = database.add_monitored_profile(
        username=data.username,
        display_name=data.display_name or "",
        avatar_url=data.avatar_url or ""
    )
    if not success:
        raise HTTPException(status_code=400, detail="Não foi possível cadastrar o perfil.")
    return {"status": "success", "username": data.username.strip().lower().lstrip("@")}

@app.patch("/api/monitored/{username}")
async def toggle_monitored(username: str, data: ToggleActiveRequest):
    success = database.toggle_profile_active(username, data.is_active)
    if not success:
        raise HTTPException(status_code=404, detail="Perfil não encontrado.")
    return {"status": "success", "is_active": data.is_active}

@app.delete("/api/monitored/{username}")
async def delete_monitored(username: str):
    success = database.delete_monitored_profile(username)
    if not success:
        raise HTTPException(status_code=404, detail="Perfil não encontrado.")
    return {"status": "success", "deleted": username}

@app.post("/api/sync-now")
async def trigger_sync(background_tasks: BackgroundTasks):
    background_tasks.add_task(scheduler.run_all_monitored_sync, scraper)
    return {"status": "started", "message": "Sincronização iniciada em segundo plano."}

@app.get("/api/scheduler-status")
async def scheduler_status():
    return scheduler.get_scheduler_status()

# --- Rotas de Downloads ---

@app.post("/api/download-single")
async def download_single(data: DownloadSingleRequest):
    target = await downloader.download_story_media(data.story, data.username, skip_if_exists=False)
    if not target:
        raise HTTPException(status_code=500, detail="Não foi possível baixar esta mídia.")
    
    clean_user = data.username.strip().lower().lstrip("@")
    return {
        "status": "success",
        "filename": target.name,
        "url": f"/downloads/{clean_user}/{target.name}"
    }

@app.post("/api/download-all/{username}")
async def download_all(username: str):
    clean_user = username.strip().lower().lstrip("@")
    profile = await scraper.get_stories(clean_user)
    
    downloaded = []
    for story in profile.stories:
        path = await downloader.download_story_media(story, clean_user, skip_if_exists=False)
        if path:
            downloaded.append({
                "story_id": story.story_id,
                "filename": path.name,
                "url": f"/downloads/{clean_user}/{path.name}"
            })

    return {
        "status": "success",
        "total_stories": profile.story_count,
        "downloaded_count": len(downloaded),
        "files": downloaded
    }

@app.get("/api/downloads")
async def get_downloads(username: Optional[str] = None):
    return downloader.list_downloaded_files(username=username)

@app.get("/api/stats")
async def get_stats():
    stats = database.get_stats()
    scheduler_info = scheduler.get_scheduler_status()
    return {
        **stats,
        "scheduler": scheduler_info
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host=config.HOST, port=config.PORT, reload=False)

