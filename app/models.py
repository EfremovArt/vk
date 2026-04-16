from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class Order:
    id: str
    user_id: int
    peer_id: int
    status: str
    created_at: str
    updated_at: str
    service_type: str | None = None
    package_code: str | None = None
    style_code: str | None = None
    photo_paths: list[str] = field(default_factory=list)
    source_photo_urls: list[str] = field(default_factory=list)
    provider_job_id: str | None = None
    provider_status_url: str | None = None
    provider_name: str | None = None
    result_images: list[str] = field(default_factory=list)
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Order":
        return cls(**payload)

    def touch(self) -> None:
        self.updated_at = utcnow_iso()
