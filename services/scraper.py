import os
import re
import logging
import asyncio
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote
import httpx
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import config

logger = logging.getLogger(__name__)

class StoryItem(BaseModel):
    story_id: str
    media_type: str = "image"  # "image" or "video"
    media_url: str
    thumbnail_url: str
    posted_at: Optional[str] = None
    expires_at: Optional[str] = None

class UserProfile(BaseModel):
    username: str
    display_name: str = ""
    avatar_url: str = ""
    is_private: bool = False
    story_count: int = 0
    stories: List[StoryItem] = Field(default_factory=list)

class ScraperException(Exception):
    pass

class ProfileNotFoundError(ScraperException):
    pass

class ProfilePrivateError(ScraperException):
    pass

class BaseStoryProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    async def fetch_stories(self, username: str) -> UserProfile:
        pass


class DirectInstagramProvider(BaseStoryProvider):
    """
    Acessa o Instagram diretamente usando sessionid, sem Instaloader.
    Usa topsearch para obter o user ID e reels_media para os stories.
    Evita web_profile_info que causa 429 e trava 666 segundos.
    """

    _IG_APP_ID = "936619743392459"
    _UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    )

    @property
    def name(self) -> str:
        return "Instagram Direto (sessionid)"

    def is_configured(self) -> bool:
        session_id = os.getenv("IG_SESSIONID", config.IG_SESSIONID).strip()
        return bool(session_id)

    def _build_headers(self, session_id: str, ds_user_id: str) -> Dict[str, str]:
        return {
            "User-Agent": self._UA,
            "Accept": "*/*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cookie": f"sessionid={session_id}; ds_user_id={ds_user_id};",
            "X-IG-App-ID": self._IG_APP_ID,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.instagram.com/",
        }

    async def fetch_stories(self, username: str) -> UserProfile:
        if not self.is_configured():
            raise ScraperException("IG_SESSIONID nao configurado no .env.")

        clean_user = username.strip().lower().lstrip("@")

        session_id_raw = os.getenv("IG_SESSIONID", config.IG_SESSIONID).strip()
        session_id = unquote(session_id_raw)

        ds_user_id = ""
        if ":" in session_id:
            part = session_id.split(":")[0]
            if part.isdigit():
                ds_user_id = part

        headers = self._build_headers(session_id, ds_user_id)

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=headers) as client:
            user_pk, full_name, avatar_url, is_private = await self._lookup_user(client, clean_user)

            if is_private:
                raise ProfilePrivateError(f"O perfil @{clean_user} e privado.")

            stories = await self._fetch_reels(client, user_pk, clean_user)

        return UserProfile(
            username=clean_user,
            display_name=full_name or clean_user,
            avatar_url=avatar_url or "",
            is_private=is_private,
            story_count=len(stories),
            stories=stories,
        )

    async def _lookup_user(self, client: httpx.AsyncClient, username: str):
        """Retorna (pk, full_name, avatar_url, is_private) via topsearch."""
        url = "https://www.instagram.com/web/search/topsearch/"
        params = {"context": "blended", "query": username}

        try:
            res = await client.get(url, params=params)
        except Exception as e:
            raise ScraperException(f"Erro de rede ao consultar topsearch: {e}")

        if res.status_code == 401:
            raise ScraperException(
                "Sessao do Instagram expirada ou invalida (401). "
                "Atualize o IG_SESSIONID no .env."
            )
        if res.status_code != 200:
            raise ScraperException(
                f"topsearch retornou status {res.status_code}. "
                "Verifique se o IG_SESSIONID esta correto."
            )

        try:
            data = res.json()
        except Exception:
            raise ScraperException("Resposta invalida do Instagram (topsearch).")

        users = data.get("users", [])
        for entry in users:
            user = entry.get("user", {})
            if user.get("username", "").lower() == username.lower():
                pk = str(user.get("pk") or user.get("id") or "")
                full_name = user.get("full_name", "") or ""
                avatar_url = user.get("profile_pic_url", "") or ""
                is_private = bool(user.get("is_private", False))
                return pk, full_name, avatar_url, is_private

        raise ProfileNotFoundError(f"Perfil @{username} nao encontrado no Instagram.")

    async def _fetch_reels(self, client: httpx.AsyncClient, user_pk: str, username: str) -> List[StoryItem]:
        """Busca stories via reels_media."""
        url = "https://www.instagram.com/api/v1/feed/reels_media/"
        params = {"user_ids": user_pk}

        try:
            res = await client.get(url, params=params)
        except Exception as e:
            raise ScraperException(f"Erro de rede ao buscar stories: {e}")

        if res.status_code == 401:
            raise ScraperException(
                "Sessao expirada ao buscar stories (401). "
                "Atualize o IG_SESSIONID no .env."
            )
        if res.status_code != 200:
            raise ScraperException(f"reels_media retornou status {res.status_code}.")

        try:
            data = res.json()
        except Exception:
            raise ScraperException("Resposta invalida do Instagram (reels_media).")

        reels = data.get("reels", {})
        reel = reels.get(user_pk) or reels.get(str(user_pk)) or {}
        items = reel.get("items", [])

        stories: List[StoryItem] = []
        for item in items:
            story_id = str(item.get("id") or item.get("pk") or "")
            media_type_code = item.get("media_type", 1)
            is_video = media_type_code == 2

            media_url = ""
            thumb_url = ""

            if is_video:
                vv = item.get("video_versions", [])
                if vv:
                    media_url = vv[0].get("url", "")
                iv = item.get("image_versions2", {}).get("candidates", [])
                thumb_url = iv[0].get("url", "") if iv else media_url
            else:
                iv = item.get("image_versions2", {}).get("candidates", [])
                media_url = iv[0].get("url", "") if iv else ""
                thumb_url = media_url

            if not media_url:
                continue

            taken_at = item.get("taken_at")
            posted_str = None
            if taken_at:
                try:
                    posted_str = datetime.fromtimestamp(int(taken_at), timezone.utc).isoformat()
                except Exception:
                    posted_str = datetime.now(timezone.utc).isoformat()

            stories.append(StoryItem(
                story_id=story_id,
                media_type="video" if is_video else "image",
                media_url=media_url,
                thumbnail_url=thumb_url or media_url,
                posted_at=posted_str,
            ))

        return stories


class StoriesIGProvider(BaseStoryProvider):
    @property
    def name(self) -> str:
        return "StoriesIG Mirror"

    async def fetch_stories(self, username: str) -> UserProfile:
        clean_user = username.strip().lower().lstrip("@")
        url = "https://storiesig.info/api/ig/story"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Referer": "https://storiesig.info/",
            "Accept": "application/json, text/plain, */*",
        }

        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            try:
                res = await client.get(url, params={"url": clean_user}, headers=headers)
                if res.status_code == 404:
                    raise ProfileNotFoundError(f"Perfil @{clean_user} nao encontrado.")
                if res.status_code != 200:
                    raise ScraperException(f"StoriesIG status {res.status_code}")
                data = res.json()
                return self._parse_response(clean_user, data)
            except (ProfileNotFoundError, ProfilePrivateError):
                raise
            except Exception as e:
                logger.warning(f"StoriesIG falhou: {e}")
                raise ScraperException(f"StoriesIG falhou: {e}")

    def _parse_response(self, username: str, data: Dict[str, Any]) -> UserProfile:
        if not data or not isinstance(data, dict):
            raise ScraperException("Resposta invalida do StoriesIG.")

        user_info = data.get("user", {}) or data.get("result", {}).get("user", {})
        display_name = user_info.get("full_name") or user_info.get("name") or username
        avatar_url = user_info.get("profile_pic_url") or user_info.get("avatar") or ""
        is_private = bool(user_info.get("is_private", False))

        if is_private:
            raise ProfilePrivateError(f"O perfil @{username} e privado.")

        raw_stories = data.get("stories") or data.get("result", {}).get("stories") or []
        parsed_stories: List[StoryItem] = []

        for idx, item in enumerate(raw_stories):
            story_id = str(item.get("id") or item.get("pk") or f"{username}_{idx}")
            is_video = bool(item.get("is_video") or item.get("media_type") == 2 or item.get("video_url"))
            media_type = "video" if is_video else "image"
            media_url = item.get("video_url") if is_video else (item.get("image_url") or item.get("display_url"))
            thumb_url = item.get("thumbnail_url") or item.get("image_url") or media_url

            if not media_url:
                continue

            posted_at = item.get("taken_at")
            posted_str = None
            if posted_at:
                try:
                    if isinstance(posted_at, (int, float)):
                        posted_str = datetime.fromtimestamp(posted_at, timezone.utc).isoformat()
                    else:
                        posted_str = str(posted_at)
                except Exception:
                    posted_str = datetime.now(timezone.utc).isoformat()

            parsed_stories.append(StoryItem(
                story_id=story_id,
                media_type=media_type,
                media_url=media_url,
                thumbnail_url=thumb_url or media_url,
                posted_at=posted_str
            ))

        return UserProfile(
            username=username,
            display_name=display_name,
            avatar_url=avatar_url,
            is_private=is_private,
            story_count=len(parsed_stories),
            stories=parsed_stories
        )


class AnonyIGProvider(BaseStoryProvider):
    @property
    def name(self) -> str:
        return "AnonyIG Mirror"

    async def fetch_stories(self, username: str) -> UserProfile:
        clean_user = username.strip().lower().lstrip("@")
        url = "https://anonyig.com/api/ig/story"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Referer": "https://anonyig.com/",
            "Accept": "application/json, text/plain, */*",
        }

        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            try:
                res = await client.get(url, params={"url": clean_user}, headers=headers)
                if res.status_code == 404:
                    raise ProfileNotFoundError(f"Perfil @{clean_user} nao encontrado.")
                if res.status_code != 200:
                    raise ScraperException(f"AnonyIG status {res.status_code}")

                data = res.json()
                items = data.get("result", {}).get("stories") or data.get("stories") or []
                user = data.get("result", {}).get("user") or data.get("user") or {}

                if user.get("is_private"):
                    raise ProfilePrivateError(f"O perfil @{clean_user} e privado.")

                parsed_stories = []
                for idx, it in enumerate(items):
                    story_id = str(it.get("id") or f"{clean_user}_{idx}")
                    is_v = bool(it.get("is_video") or it.get("video_url"))
                    m_url = it.get("video_url") if is_v else (it.get("image_url") or it.get("display_url"))
                    if not m_url:
                        continue
                    parsed_stories.append(StoryItem(
                        story_id=story_id,
                        media_type="video" if is_v else "image",
                        media_url=m_url,
                        thumbnail_url=it.get("thumbnail_url") or m_url,
                        posted_at=datetime.now(timezone.utc).isoformat()
                    ))

                return UserProfile(
                    username=clean_user,
                    display_name=user.get("full_name") or clean_user,
                    avatar_url=user.get("profile_pic_url") or "",
                    is_private=False,
                    story_count=len(parsed_stories),
                    stories=parsed_stories
                )
            except (ProfileNotFoundError, ProfilePrivateError):
                raise
            except Exception as e:
                logger.warning(f"AnonyIG falhou: {e}")
                raise ScraperException(f"AnonyIG falhou: {e}")


class StoryScraper:
    def __init__(self, providers: Optional[List[BaseStoryProvider]] = None):
        self._custom_providers = providers

    def _get_providers(self) -> List[BaseStoryProvider]:
        if self._custom_providers:
            return self._custom_providers

        providers = []
        direct_prov = DirectInstagramProvider()
        if direct_prov.is_configured():
            providers.append(direct_prov)

        providers.extend([
            StoriesIGProvider(),
            AnonyIGProvider()
        ])
        return providers

    async def get_stories(self, username: str) -> UserProfile:
        clean_user = username.strip().lower().lstrip("@")
        if not clean_user or not re.match(r"^[a-zA-Z0-9._]{1,30}$", clean_user):
            raise ScraperException(f"Nome de usuario invalido: '{username}'")

        providers = self._get_providers()
        last_error = None

        for provider in providers:
            try:
                logger.info(f"Consultando stories de @{clean_user} usando '{provider.name}'...")
                profile = await provider.fetch_stories(clean_user)
                logger.info(f"Sucesso com '{provider.name}': {profile.story_count} stories encontrados.")
                return profile
            except (ProfileNotFoundError, ProfilePrivateError):
                raise
            except Exception as e:
                logger.warning(f"Provedor '{provider.name}' falhou: {e}. Tentando fallback...")
                last_error = e

        has_session = bool(os.getenv("IG_SESSIONID", config.IG_SESSIONID))
        hint = "" if has_session else (
            " Dica: Configure o IG_SESSIONID no arquivo .env para acesso direto e estavel."
        )

        raise ScraperException(
            f"Nao foi possivel obter os stories de @{clean_user} no momento.{hint} (Detalhes: {last_error})"
        )
