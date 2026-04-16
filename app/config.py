from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SERVICE_TYPES = {
    "portrait": "Нейрофотосессия",
    "marketplace": "Карточки для маркетплейсов",
}

SERVICE_LABEL_TO_CODE = {value.lower(): key for key, value in SERVICE_TYPES.items()}

# ── Portrait catalogs ──────────────────────────────────────────────

PACKAGE_CATALOG = {
    "lite": {
        "label": "Lite - 10 кадров",
        "description": "10 готовых портретов в одном стиле",
        "expected_result": 10,
    },
    "pro": {
        "label": "Pro - 20 кадров",
        "description": "20 кадров и 2 варианта обработки",
        "expected_result": 20,
    },
    "premium": {
        "label": "Premium - 35 кадров",
        "description": "35 кадров, 3 стилистики и приоритетная очередь",
        "expected_result": 35,
    },
}

STYLE_CATALOG = {
    "business": "Бизнес-портрет",
    "fashion": "Fashion / глянец",
    "travel": "Путешествие",
    "cinematic": "Кинематографичный стиль",
}

PACKAGE_LABEL_TO_CODE = {value["label"].lower(): key for key, value in PACKAGE_CATALOG.items()}
STYLE_LABEL_TO_CODE = {value.lower(): key for key, value in STYLE_CATALOG.items()}

# ── Marketplace catalogs ───────────────────────────────────────────

MARKETPLACE_PACKAGE_CATALOG = {
    "mp_starter": {
        "label": "Starter - 5 карточек",
        "description": "5 профессиональных карточек товара в едином стиле",
        "expected_result": 5,
    },
    "mp_standard": {
        "label": "Standard - 15 карточек",
        "description": "15 карточек, 3 ракурса, инфографика",
        "expected_result": 15,
    },
    "mp_full": {
        "label": "Full - 30 карточек",
        "description": "30 карточек, все ракурсы, лайфстайл + инфографика + A/B-варианты",
        "expected_result": 30,
    },
}

MARKETPLACE_STYLE_CATALOG = {
    "white_bg": "Белый фон (студия)",
    "lifestyle": "Лайфстайл (в интерьере)",
    "infographic": "Инфографика",
    "flatlay": "Flat-lay раскладка",
    "model_hand": "На модели / в руке",
    "gradient": "Градиентный фон",
}

MARKETPLACE_PACKAGE_LABEL_TO_CODE = {
    value["label"].lower(): key for key, value in MARKETPLACE_PACKAGE_CATALOG.items()
}
MARKETPLACE_STYLE_LABEL_TO_CODE = {
    value.lower(): key for key, value in MARKETPLACE_STYLE_CATALOG.items()
}

# ── Settings ───────────────────────────────────────────────────────

MARKETPLACE_MIN_PHOTOS = 3
MARKETPLACE_MAX_PHOTOS = 10


@dataclass(slots=True)
class Settings:
    vk_bot_token: str
    data_dir: Path
    orders_file: Path
    photos_dir: Path
    min_photos: int
    max_photos: int
    generation_api_base_url: str | None
    generation_api_token: str | None
    generation_timeout_sec: int


def _get_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value == "":
        return default
    return int(raw_value)


def get_settings() -> Settings:
    data_dir = BASE_DIR / "data"
    return Settings(
        vk_bot_token=os.getenv("VK_BOT_TOKEN", "").strip(),
        data_dir=data_dir,
        orders_file=data_dir / "orders.json",
        photos_dir=data_dir / "photos",
        min_photos=_get_int_env("MIN_PHOTOS", 8),
        max_photos=_get_int_env("MAX_PHOTOS", 15),
        generation_api_base_url=os.getenv("GENERATION_API_BASE_URL", "").strip() or None,
        generation_api_token=os.getenv("GENERATION_API_TOKEN", "").strip() or None,
        generation_timeout_sec=_get_int_env("GENERATION_TIMEOUT_SEC", 120),
    )
