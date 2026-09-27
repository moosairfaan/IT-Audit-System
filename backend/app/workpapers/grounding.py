"""Reject workpaper text that introduces a number the test result does not contain."""

from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any

_IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")
_DATETIME = re.compile(
    r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)?"
)
_NUMBER = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")
_PLAIN_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


class GroundingError(ValueError):
    """The draft contains a number or identifier that is not in the source result."""


def check_grounding(text: str, source: dict[str, Any]) -> None:
    raw = json.dumps(source, ensure_ascii=False, default=str)
    allowed = _numbers(source)
    masked = _mask_dates(text, raw)
    masked = _mask_identifiers(masked, raw)
    unsupported: list[str] = []
    for match in _NUMBER.finditer(masked):
        token = match.group(0)
        if _normalize(token) not in allowed:
            unsupported.append(token)
    if unsupported:
        listed = ", ".join(unsupported)
        raise GroundingError(f"Workpaper contains numbers that are not in the source data: {listed}")


def _numbers(value: Any) -> set[Decimal]:
    found: set[Decimal] = set()

    def walk(item: Any) -> None:
        if isinstance(item, bool) or item is None:
            return
        if isinstance(item, int):
            found.add(_normalize(str(item)))
            return
        if isinstance(item, float):
            found.add(_normalize(str(item)))
            return
        if isinstance(item, str):
            if _PLAIN_NUMBER.fullmatch(item.strip()):
                found.add(_normalize(item.strip()))
            return
        if isinstance(item, dict):
            for child in item.values():
                walk(child)
            return
        if isinstance(item, list):
            for child in item:
                walk(child)

    walk(value)
    return found


def _mask_identifiers(text: str, source_text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        if not any(character.isdigit() for character in token):
            return token
        if token not in source_text:
            raise GroundingError(
                f"Workpaper contains an identifier that is not in the source data: {token}"
            )
        return " " * len(token)

    return _IDENTIFIER.sub(replace, text)


def _mask_dates(text: str, source_text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        if token not in source_text:
            return token
        return " " * len(token)

    return _DATETIME.sub(replace, text)


def _normalize(token: str) -> Decimal:
    return Decimal(token.replace(",", "")).normalize()
