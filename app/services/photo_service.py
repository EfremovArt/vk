from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import aiohttp

from app.models import Order


class PhotoDownloadError(RuntimeError):
    pass


class PhotoService:
    def __init__(self, photos_dir: Path) -> None:
        self.photos_dir = photos_dir
        self.photos_dir.mkdir(parents=True, exist_ok=True)

    async def store_message_photos(self, order: Order, photo_urls: list[str]) -> list[str]:
        if not photo_urls:
            return []

        order_dir = self.photos_dir / order.id
        order_dir.mkdir(parents=True, exist_ok=True)

        saved_paths: list[str] = []
        async with aiohttp.ClientSession() as session:
            for index, photo_url in enumerate(photo_urls, start=len(order.photo_paths) + 1):
                saved_path = order_dir / self._build_filename(index, photo_url)
                await self._download(session, photo_url, saved_path)
                saved_paths.append(str(saved_path))
        return saved_paths

    def _build_filename(self, index: int, photo_url: str) -> str:
        parsed = urlparse(photo_url)
        suffix = Path(parsed.path).suffix or ".jpg"
        return f"photo_{index:02d}{suffix}"

    async def _download(self, session: aiohttp.ClientSession, photo_url: str, target_path: Path) -> None:
        async with session.get(photo_url) as response:
            if response.status >= 400:
                raise PhotoDownloadError(f"Не удалось скачать фотографию: {response.status}")
            target_path.write_bytes(await response.read())
