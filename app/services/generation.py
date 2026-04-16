from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiohttp

from app.config import Settings
from app.models import Order


@dataclass(slots=True)
class SubmissionResult:
    provider_name: str
    job_id: str | None
    status: str
    status_url: str | None = None
    message: str | None = None


@dataclass(slots=True)
class StatusResult:
    provider_name: str
    status: str
    result_images: list[str]
    error_message: str | None = None


class BaseGenerationClient:
    provider_name = "base"

    async def submit_order(self, order: Order) -> SubmissionResult:
        raise NotImplementedError

    async def fetch_status(self, order: Order) -> StatusResult:
        raise NotImplementedError


class MockGenerationClient(BaseGenerationClient):
    provider_name = "mock"

    async def submit_order(self, order: Order) -> SubmissionResult:
        return SubmissionResult(
            provider_name=self.provider_name,
            job_id=f"mock-{order.id[:8]}",
            status="pending_provider",
            message="Внешний генератор не настроен. Заявка сохранена локально.",
        )

    async def fetch_status(self, order: Order) -> StatusResult:
        return StatusResult(
            provider_name=self.provider_name,
            status=order.status,
            result_images=order.result_images,
            error_message=order.error_message,
        )


class HttpGenerationClient(BaseGenerationClient):
    provider_name = "http"

    def __init__(self, base_url: str, token: str | None, timeout_sec: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = aiohttp.ClientTimeout(total=timeout_sec)

    async def submit_order(self, order: Order) -> SubmissionResult:
        form = aiohttp.FormData()
        form.add_field("order_id", order.id)
        form.add_field("vk_user_id", str(order.user_id))
        form.add_field("package_code", order.package_code or "")
        form.add_field("style_code", order.style_code or "")

        file_handles = [Path(path).open("rb") for path in order.photo_paths]
        try:
            for index, file_handle in enumerate(file_handles, start=1):
                form.add_field(
                    f"image_{index}",
                    file_handle,
                    filename=Path(file_handle.name).name,
                    content_type="image/jpeg",
                )

            async with aiohttp.ClientSession(timeout=self.timeout, headers=self._headers()) as session:
                async with session.post(f"{self.base_url}/jobs", data=form) as response:
                    payload = await self._decode_response(response)
        finally:
            for file_handle in file_handles:
                file_handle.close()

        return SubmissionResult(
            provider_name=self.provider_name,
            job_id=payload.get("job_id"),
            status=payload.get("status", "queued"),
            status_url=payload.get("status_url"),
            message=payload.get("message"),
        )

    async def fetch_status(self, order: Order) -> StatusResult:
        if not order.provider_job_id:
            return StatusResult(
                provider_name=self.provider_name,
                status=order.status,
                result_images=order.result_images,
                error_message=order.error_message,
            )

        status_url = order.provider_status_url or f"{self.base_url}/jobs/{order.provider_job_id}"
        async with aiohttp.ClientSession(timeout=self.timeout, headers=self._headers()) as session:
            async with session.get(status_url) as response:
                payload = await self._decode_response(response)

        result_images = payload.get("result_images") or payload.get("images") or []
        return StatusResult(
            provider_name=self.provider_name,
            status=payload.get("status", order.status),
            result_images=result_images,
            error_message=payload.get("error") or payload.get("error_message"),
        )

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def _decode_response(self, response: aiohttp.ClientResponse) -> dict[str, Any]:
        payload = await response.json(content_type=None)
        if response.status >= 400:
            message = payload.get("message") or payload.get("error") or str(payload)
            raise RuntimeError(message)
        if not isinstance(payload, dict):
            raise RuntimeError("Провайдер генерации вернул неожиданный формат ответа")
        return payload


def build_generation_client(settings: Settings) -> BaseGenerationClient:
    if settings.generation_api_base_url:
        return HttpGenerationClient(
            base_url=settings.generation_api_base_url,
            token=settings.generation_api_token,
            timeout_sec=settings.generation_timeout_sec,
        )
    return MockGenerationClient()
