from __future__ import annotations

from vkbottle import Keyboard, KeyboardButtonColor, Text

from app.config import (
    MARKETPLACE_PACKAGE_CATALOG,
    MARKETPLACE_STYLE_CATALOG,
    PACKAGE_CATALOG,
    SERVICE_TYPES,
    STYLE_CATALOG,
)


def package_keyboard() -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    package_codes = list(PACKAGE_CATALOG.keys())
    for index, package_code in enumerate(package_codes):
        keyboard.add(Text(PACKAGE_CATALOG[package_code]["label"]), color=KeyboardButtonColor.PRIMARY)
        if index < len(package_codes) - 1:
            keyboard.row()
    return keyboard.get_json()


def style_keyboard() -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    style_codes = list(STYLE_CATALOG.keys())
    for index, style_code in enumerate(style_codes):
        keyboard.add(Text(STYLE_CATALOG[style_code]), color=KeyboardButtonColor.SECONDARY)
        if index % 2 == 1 and index < len(style_codes) - 1:
            keyboard.row()
    return keyboard.get_json()


def photo_keyboard() -> str:
    return (
        Keyboard(one_time=False, inline=False)
        .add(Text("Готово"), color=KeyboardButtonColor.POSITIVE)
        .row()
        .add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
        .get_json()
    )


def service_type_keyboard() -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    for index, (code, label) in enumerate(SERVICE_TYPES.items()):
        keyboard.add(Text(label), color=KeyboardButtonColor.PRIMARY)
        if index < len(SERVICE_TYPES) - 1:
            keyboard.row()
    keyboard.row()
    keyboard.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()


def marketplace_package_keyboard() -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    codes = list(MARKETPLACE_PACKAGE_CATALOG.keys())
    for index, code in enumerate(codes):
        keyboard.add(Text(MARKETPLACE_PACKAGE_CATALOG[code]["label"]), color=KeyboardButtonColor.PRIMARY)
        if index < len(codes) - 1:
            keyboard.row()
    return keyboard.get_json()


def marketplace_style_keyboard() -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    codes = list(MARKETPLACE_STYLE_CATALOG.keys())
    for index, code in enumerate(codes):
        keyboard.add(Text(MARKETPLACE_STYLE_CATALOG[code]), color=KeyboardButtonColor.SECONDARY)
        if index % 2 == 1 and index < len(codes) - 1:
            keyboard.row()
    return keyboard.get_json()


def start_keyboard() -> str:
    return (
        Keyboard(one_time=False, inline=False)
        .add(Text("Начать"), color=KeyboardButtonColor.POSITIVE)
        .row()
        .add(Text("Статус"), color=KeyboardButtonColor.PRIMARY)
        .add(Text("Помощь"), color=KeyboardButtonColor.SECONDARY)
        .get_json()
    )
