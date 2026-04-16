from __future__ import annotations

from typing import Iterable

from vkbottle import BaseStateGroup
from vkbottle.bot import Bot, Message

from app.config import (
    MARKETPLACE_MAX_PHOTOS,
    MARKETPLACE_MIN_PHOTOS,
    MARKETPLACE_PACKAGE_CATALOG,
    MARKETPLACE_PACKAGE_LABEL_TO_CODE,
    MARKETPLACE_STYLE_CATALOG,
    MARKETPLACE_STYLE_LABEL_TO_CODE,
    PACKAGE_CATALOG,
    PACKAGE_LABEL_TO_CODE,
    SERVICE_LABEL_TO_CODE,
    SERVICE_TYPES,
    STYLE_CATALOG,
    STYLE_LABEL_TO_CODE,
    get_settings,
)
from app.keyboards import (
    marketplace_package_keyboard,
    marketplace_style_keyboard,
    package_keyboard,
    photo_keyboard,
    service_type_keyboard,
    start_keyboard,
    style_keyboard,
)
from app.models import Order
from app.services.generation import BaseGenerationClient, build_generation_client
from app.services.photo_service import PhotoDownloadError, PhotoService
from app.storage import OrderRepository

settings = get_settings()
if not settings.vk_bot_token:
    raise RuntimeError("Не задан VK_BOT_TOKEN. Создайте .env на основе .env.example")

bot = Bot(settings.vk_bot_token)
repository = OrderRepository(settings.orders_file)
photo_service = PhotoService(settings.photos_dir)
generation_client = build_generation_client(settings)


class SessionState(BaseStateGroup):
    SELECT_SERVICE = "select_service"
    SELECT_PACKAGE = "select_package"
    SELECT_STYLE = "select_style"
    COLLECT_PHOTOS = "collect_photos"


FINAL_STATUSES = {"done", "failed", "cancelled"}

PHOTO_TIPS_PORTRAIT = (
    "Лучше всего подходят фото с разным ракурсом, нейтральным светом и без сильных фильтров."
)

PHOTO_TIPS_MARKETPLACE = (
    "Советы для лучшего результата:\n"
    "- Сфотографируй товар на однотонном фоне (белый / серый).\n"
    "- Сделай несколько ракурсов: спереди, сбоку, сверху, деталь крупным планом.\n"
    "- Используй равномерное освещение без резких теней.\n"
    "- Избегай сильных фильтров и водяных знаков."
)


# ── Helpers: catalog selectors per service type ──────────────────────

def _pkg_catalog(order: Order) -> dict:
    if order.service_type == "marketplace":
        return MARKETPLACE_PACKAGE_CATALOG
    return PACKAGE_CATALOG


def _style_catalog(order: Order) -> dict:
    if order.service_type == "marketplace":
        return MARKETPLACE_STYLE_CATALOG
    return STYLE_CATALOG


def _min_photos(order: Order) -> int:
    if order.service_type == "marketplace":
        return MARKETPLACE_MIN_PHOTOS
    return settings.min_photos


def _max_photos(order: Order) -> int:
    if order.service_type == "marketplace":
        return MARKETPLACE_MAX_PHOTOS
    return settings.max_photos


def _pkg_keyboard(order: Order) -> str:
    if order.service_type == "marketplace":
        return marketplace_package_keyboard()
    return package_keyboard()


def _style_keyboard(order: Order) -> str:
    if order.service_type == "marketplace":
        return marketplace_style_keyboard()
    return style_keyboard()


def _photo_tips(order: Order) -> str:
    if order.service_type == "marketplace":
        return PHOTO_TIPS_MARKETPLACE
    return PHOTO_TIPS_PORTRAIT


# ── Handlers ─────────────────────────────────────────────────────────

@bot.on.message(text=["/start", "Начать", "Начать фотосессию", "start"])
async def start_handler(message: Message) -> None:
    order = repository.create_draft(user_id=message.from_id, peer_id=message.peer_id)
    order.status = "draft"
    repository.save(order)
    await bot.state_dispenser.set(message.peer_id, SessionState.SELECT_SERVICE, order_id=order.id)
    await message.answer(
        "Привет! Выбери, что тебе нужно:\n\n"
        "1. Нейрофотосессия — профессиональные портреты по твоим фотографиям.\n"
        "2. Карточки для маркетплейсов — студийные фото товаров для WB, Ozon, Яндекс Маркет и др.",
        keyboard=service_type_keyboard(),
    )


@bot.on.message(text=["/help", "Помощь", "help"])
async def help_handler(message: Message) -> None:
    await message.answer(
        "Я умею делать:\n\n"
        "— Нейрофотосессию: профессиональные портреты на основе твоих фото.\n"
        "— Карточки для маркетплейсов: студийные фото товаров, как из фотостудии.\n\n"
        "Сценарий работы:\n"
        "1. Нажми 'Начать'.\n"
        "2. Выбери тип услуги, пакет и стиль.\n"
        "3. Отправь фотографии.\n"
        "4. Нажми 'Готово', и я отправлю заявку в генерацию.",
        keyboard=start_keyboard(),
    )


@bot.on.message(text=["/status", "Статус", "status"])
async def status_handler(message: Message) -> None:
    order = repository.get_last_order_for_user(message.from_id)
    if order is None:
        await message.answer("У тебя пока нет заявок. Нажми 'Начать'.", keyboard=start_keyboard())
        return

    order = await refresh_order_status(order, generation_client)
    await message.answer(format_order_status(order), keyboard=start_keyboard())


@bot.on.message(text=["/cancel", "Отмена", "cancel"])
async def cancel_handler(message: Message) -> None:
    order = repository.get_active_order_for_user(message.from_id)
    if order is None:
        await bot.state_dispenser.delete(message.peer_id)
        await message.answer("Активной заявки нет.", keyboard=start_keyboard())
        return

    order.status = "cancelled"
    repository.save(order)
    await bot.state_dispenser.delete(message.peer_id)
    await message.answer(
        "Заявка отменена. Если захочешь начать заново, нажми 'Начать'.",
        keyboard=start_keyboard(),
    )


# ── Service type ─────────────────────────────────────────────────────

@bot.on.message(state=SessionState.SELECT_SERVICE)
async def service_selection_handler(message: Message) -> None:
    service_code = parse_service_type(message.text)
    if not service_code:
        await message.answer(
            "Выбери тип услуги на клавиатуре ниже.",
            keyboard=service_type_keyboard(),
        )
        return

    order = repository.create_draft(user_id=message.from_id, peer_id=message.peer_id)
    order.service_type = service_code
    order.status = "service_selected"
    repository.save(order)
    await bot.state_dispenser.set(message.peer_id, SessionState.SELECT_PACKAGE, order_id=order.id)
    await message.answer(
        f"Отлично, {SERVICE_TYPES[service_code]}! Теперь выбери пакет.",
        keyboard=_pkg_keyboard(order),
    )


# ── Package ──────────────────────────────────────────────────────────

@bot.on.message(state=SessionState.SELECT_PACKAGE)
async def package_selection_handler(message: Message) -> None:
    order = repository.create_draft(user_id=message.from_id, peer_id=message.peer_id)
    package_code = parse_package(message.text, order)
    if not package_code:
        await message.answer(
            "Выбери один из пакетов на клавиатуре ниже.",
            keyboard=_pkg_keyboard(order),
        )
        return

    order.package_code = package_code
    order.status = "package_selected"
    repository.save(order)
    await bot.state_dispenser.set(message.peer_id, SessionState.SELECT_STYLE, order_id=order.id)
    catalog = _pkg_catalog(order)
    await message.answer(
        f"Пакет '{catalog[package_code]['label']}' выбран. Теперь выбери стиль.",
        keyboard=_style_keyboard(order),
    )


# ── Style ────────────────────────────────────────────────────────────

@bot.on.message(state=SessionState.SELECT_STYLE)
async def style_selection_handler(message: Message) -> None:
    order = repository.create_draft(user_id=message.from_id, peer_id=message.peer_id)
    style_code = parse_style(message.text, order)
    if not style_code:
        await message.answer(
            "Выбери стиль на клавиатуре ниже.",
            keyboard=_style_keyboard(order),
        )
        return

    order.style_code = style_code
    order.status = "collecting_photos"
    repository.save(order)
    await bot.state_dispenser.set(message.peer_id, SessionState.COLLECT_PHOTOS, order_id=order.id)

    min_p = _min_photos(order)
    max_p = _max_photos(order)
    tips = _photo_tips(order)
    await message.answer(
        f"Теперь пришли фотографии. Нужно минимум {min_p}, максимум {max_p}.\n\n"
        f"{tips}\n\n"
        "Когда закончишь, нажми 'Готово'.",
        keyboard=photo_keyboard(),
    )


# ── Photo collection ─────────────────────────────────────────────────

@bot.on.message(state=SessionState.COLLECT_PHOTOS)
async def photo_collection_handler(message: Message) -> None:
    order = repository.get_active_order_for_user(message.from_id)
    if order is None:
        await bot.state_dispenser.delete(message.peer_id)
        await message.answer("Не нашёл активную заявку. Нажми 'Начать'.", keyboard=start_keyboard())
        return

    text = (message.text or "").strip().lower()
    if text in {"готово", "/done", "done"}:
        await finalize_order(message, order)
        return

    photo_urls = extract_photo_urls(message)
    if not photo_urls:
        await message.answer(
            "Я жду фотографии. Отправь одно или несколько фото сообщением, либо нажми 'Готово'.",
            keyboard=photo_keyboard(),
        )
        return

    max_p = _max_photos(order)
    min_p = _min_photos(order)

    if len(order.photo_paths) >= max_p:
        await message.answer(
            f"Уже загружен максимум: {max_p} фото. Нажми 'Готово' для запуска.",
            keyboard=photo_keyboard(),
        )
        return

    allowed_count = max_p - len(order.photo_paths)
    limited_photo_urls = photo_urls[:allowed_count]

    try:
        saved_paths = await photo_service.store_message_photos(order, limited_photo_urls)
    except PhotoDownloadError as error:
        await message.answer(f"Не удалось сохранить фото: {error}")
        return

    order.photo_paths.extend(saved_paths)
    order.source_photo_urls.extend(limited_photo_urls)
    order.status = "collecting_photos"
    repository.save(order)

    uploaded_count = len(order.photo_paths)
    if uploaded_count >= max_p:
        await message.answer(
            f"Загружено {uploaded_count} фото. Достигнут максимум, запускаю заявку.",
            keyboard=photo_keyboard(),
        )
        await finalize_order(message, order)
        return

    await message.answer(
        f"Сохранено фото: {uploaded_count}/{max_p}. "
        f"Минимум для запуска: {min_p}.",
        keyboard=photo_keyboard(),
    )


# ── Fallback ─────────────────────────────────────────────────────────

@bot.on.message()
async def fallback_handler(message: Message) -> None:
    await message.answer(
        "Напиши 'Начать', чтобы создать новую заявку, или 'Статус', чтобы проверить текущую.",
        keyboard=start_keyboard(),
    )


# ── Finalization ─────────────────────────────────────────────────────

async def finalize_order(message: Message, order: Order) -> None:
    min_p = _min_photos(order)
    if len(order.photo_paths) < min_p:
        await message.answer(
            f"Пока недостаточно материалов. Сейчас загружено {len(order.photo_paths)} фото, "
            f"а нужно минимум {min_p}.",
            keyboard=photo_keyboard(),
        )
        return

    order.status = "submitting"
    repository.save(order)

    try:
        submission = await generation_client.submit_order(order)
    except Exception as error:
        order.status = "failed"
        order.error_message = str(error)
        repository.save(order)
        await bot.state_dispenser.delete(message.peer_id)
        await message.answer(
            "Не удалось передать заявку в генерацию. Попробуй позже или проверь настройки провайдера.\n\n"
            f"Ошибка: {error}",
            keyboard=start_keyboard(),
        )
        return

    order.provider_name = submission.provider_name
    order.provider_job_id = submission.job_id
    order.provider_status_url = submission.status_url
    order.status = submission.status
    order.error_message = submission.message
    repository.save(order)
    await bot.state_dispenser.delete(message.peer_id)

    pkg_catalog = _pkg_catalog(order)
    sty_catalog = _style_catalog(order)
    service_label = SERVICE_TYPES.get(order.service_type or "", "—")

    reply = [
        "Заявка принята в работу.",
        f"ID заказа: {order.id}",
        f"Услуга: {service_label}",
        f"Пакет: {pkg_catalog.get(order.package_code or '', {}).get('label', 'не выбран')}",
        f"Стиль: {sty_catalog.get(order.style_code or '', 'не выбран')}",
        f"Фото: {len(order.photo_paths)}",
        f"Статус: {order.status}",
    ]
    if submission.job_id:
        reply.append(f"Job ID: {submission.job_id}")
    if submission.message:
        reply.append(submission.message)

    await message.answer("\n".join(reply), keyboard=start_keyboard())


# ── Status refresh ───────────────────────────────────────────────────

async def refresh_order_status(order: Order, client: BaseGenerationClient) -> Order:
    if order.status in FINAL_STATUSES:
        return order

    if order.provider_name != "http":
        return order

    try:
        provider_status = await client.fetch_status(order)
    except Exception as error:
        order.error_message = str(error)
        repository.save(order)
        return order

    order.status = provider_status.status
    order.result_images = provider_status.result_images
    order.error_message = provider_status.error_message
    repository.save(order)
    return order


# ── Parsers ──────────────────────────────────────────────────────────

def parse_service_type(raw_text: str | None) -> str | None:
    if not raw_text:
        return None
    text = raw_text.strip().lower()
    if text in SERVICE_TYPES:
        return text
    return SERVICE_LABEL_TO_CODE.get(text)


def parse_package(raw_text: str | None, order: Order) -> str | None:
    if not raw_text:
        return None
    text = raw_text.strip().lower()
    if order.service_type == "marketplace":
        if text in MARKETPLACE_PACKAGE_CATALOG:
            return text
        return MARKETPLACE_PACKAGE_LABEL_TO_CODE.get(text)
    if text in PACKAGE_CATALOG:
        return text
    return PACKAGE_LABEL_TO_CODE.get(text)


def parse_style(raw_text: str | None, order: Order) -> str | None:
    if not raw_text:
        return None
    text = raw_text.strip().lower()
    if order.service_type == "marketplace":
        if text in MARKETPLACE_STYLE_CATALOG:
            return text
        return MARKETPLACE_STYLE_LABEL_TO_CODE.get(text)
    if text in STYLE_CATALOG:
        return text
    return STYLE_LABEL_TO_CODE.get(text)


def extract_photo_urls(message: Message) -> list[str]:
    urls: list[str] = []
    for attachment in iter_attachments(message):
        photo = getattr(attachment, "photo", None)
        sizes = getattr(photo, "sizes", None)
        if not sizes:
            continue
        best_size = max(
            sizes,
            key=lambda item: ((getattr(item, "height", 0) or 0) * (getattr(item, "width", 0) or 0)),
        )
        url = getattr(best_size, "url", None)
        if url:
            urls.append(url)
    return urls


def iter_attachments(message: Message) -> Iterable[object]:
    attachments = getattr(message, "attachments", None)
    if attachments is None:
        return ()
    return attachments


def format_order_status(order: Order) -> str:
    pkg_catalog = _pkg_catalog(order)
    sty_catalog = _style_catalog(order)
    service_label = SERVICE_TYPES.get(order.service_type or "", "—")
    lines = [
        f"Заказ: {order.id}",
        f"Услуга: {service_label}",
        f"Статус: {order.status}",
        f"Пакет: {pkg_catalog.get(order.package_code or '', {}).get('label', 'не выбран')}",
        f"Стиль: {sty_catalog.get(order.style_code or '', 'не выбран')}",
        f"Загружено фото: {len(order.photo_paths)}",
    ]
    if order.provider_job_id:
        lines.append(f"Job ID: {order.provider_job_id}")
    if order.error_message:
        lines.append(f"Комментарий: {order.error_message}")
    if order.result_images:
        lines.append("Результаты:")
        lines.extend(order.result_images)
    return "\n".join(lines)


if __name__ == "__main__":
    bot.run_forever()
