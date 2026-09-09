import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import config
from services import database, downloader
from services.scraper import StoryScraper, ScraperException

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
_is_syncing = False

async def sync_profile(username: str, scraper: Optional[StoryScraper] = None) -> Dict[str, Any]:
    clean_username = username.strip().lower().lstrip("@")
    scraper_instance = scraper or StoryScraper()
    
    logger.info(f"[Scheduler] Iniciando sincronizacao para @{clean_username}...")
    summary = {
        "username": clean_username,
        "success": False,
        "stories_found": 0,
        "stories_downloaded": 0,
        "error": None
    }

    try:
        profile = await scraper_instance.get_stories(clean_username)
        summary["stories_found"] = profile.story_count
        
        # Atualiza avatar e nome do perfil se disponiveis
        if profile.display_name or profile.avatar_url:
            database.add_monitored_profile(
                username=clean_username,
                display_name=profile.display_name,
                avatar_url=profile.avatar_url
            )

        downloaded_count = 0
        for story in profile.stories:
            if not database.is_story_downloaded(story.story_id):
                result = await downloader.download_story_media(story, clean_username)
                if result:
                    downloaded_count += 1

        summary["stories_downloaded"] = downloaded_count
        summary["success"] = True
        database.update_last_checked(clean_username)
        logger.info(f"[Scheduler] @{clean_username} concluido: {downloaded_count} novos stories baixados.")

    except ScraperException as se:
        logger.warning(f"[Scheduler] Aviso ao sincronizar @{clean_username}: {se}")
        summary["error"] = str(se)
    except Exception as e:
        logger.error(f"[Scheduler] Erro inesperado ao sincronizar @{clean_username}: {e}")
        summary["error"] = str(e)

    return summary

async def run_all_monitored_sync(scraper: Optional[StoryScraper] = None) -> Dict[str, Any]:
    global _is_syncing
    if _is_syncing:
        logger.info("[Scheduler] Sincronizacao ja esta em andamento. Pulando nova solicitacao.")
        return {"status": "busy", "message": "Sincronização já em execução"}

    _is_syncing = True
    start_time = datetime.now(timezone.utc)
    logger.info("[Scheduler] Iniciando rotina geral de verificacao de perfis monitorados...")
    
    results = []
    try:
        profiles = database.get_monitored_profiles(active_only=True)
        for idx, prof in enumerate(profiles):
            user = prof["username"]
            res = await sync_profile(user, scraper=scraper)
            results.append(res)
            
            # Cortesia contra rate-limit entre perfis
            if idx < len(profiles) - 1 and config.REQUEST_DELAY_SECONDS > 0:
                await asyncio.sleep(config.REQUEST_DELAY_SECONDS)

        total_downloaded = sum(r.get("stories_downloaded", 0) for r in results)
        return {
            "status": "completed",
            "started_at": start_time.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "profiles_checked": len(profiles),
            "total_new_downloads": total_downloaded,
            "details": results
        }
    finally:
        _is_syncing = False

def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(
            run_all_monitored_sync,
            trigger="interval",
            hours=config.INTERVAL_HOURS,
            id="daily_stories_sync",
            replace_existing=True,
            next_run_time=datetime.now() # Dispara primeira checagem logo apos o boot
        )
        scheduler.start()
        logger.info(f"[Scheduler] Agendador iniciado! Intervalo de execucao: a cada {config.INTERVAL_HOURS}h.")

def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[Scheduler] Agendador encerrado.")

def get_scheduler_status() -> Dict[str, Any]:
    job = scheduler.get_job("daily_stories_sync") if scheduler.running else None
    next_run = None
    if job and job.next_run_time:
        next_run = job.next_run_time.isoformat()

    return {
        "is_running": scheduler.running,
        "is_syncing": _is_syncing,
        "interval_hours": config.INTERVAL_HOURS,
        "next_run_time": next_run
    }
