"""Draw a reproducible sample from a control population."""

from __future__ import annotations

import random
import secrets
from dataclasses import dataclass

METHODS = ("random", "risk_based")


@dataclass(frozen=True, slots=True)
class PopulationItem:
    item_id: str
    priority: bool


class SamplingError(ValueError):
    """The sample request does not fit the population."""


def choose(items: list[PopulationItem], method: str, sample_size: int, seed: int) -> list[str]:
    if method not in METHODS:
        raise SamplingError("method must be random or risk_based")
    if sample_size < 1:
        raise SamplingError("sample_size must be at least 1")
    if sample_size > len(items):
        raise SamplingError(f"sample_size exceeds the population of {len(items)}")
    ordered = sorted(items, key=lambda item: item.item_id)
    generator = random.Random(seed)
    if method == "random":
        pool = [item.item_id for item in ordered]
        generator.shuffle(pool)
        return pool[:sample_size]
    priority = [item.item_id for item in ordered if item.priority]
    remainder = [item.item_id for item in ordered if not item.priority]
    generator.shuffle(priority)
    generator.shuffle(remainder)
    return (priority + remainder)[:sample_size]


def new_seed() -> int:
    return secrets.randbelow(2**31)
