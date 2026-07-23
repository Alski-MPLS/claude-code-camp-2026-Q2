"""Player vitals tracking — passive phrase detection + score parsing."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# Phrases that set flags
_THIRSTY_SET   = re.compile(r"you are thirsty", re.IGNORECASE)
_HUNGRY_SET    = re.compile(r"you are hungry", re.IGNORECASE)
_THIRSTY_CLEAR = re.compile(r"don.t feel thirsty|no longer thirsty|quench", re.IGNORECASE)
_HUNGRY_CLEAR  = re.compile(r"you are full|no longer hungry|satiat", re.IGNORECASE)

# Score formats: "Hit Points: 45/120" or "HP: 45/120"
_HP_RE = re.compile(r"(?:hit points|hp)\s*:\s*(\d+)\s*/\s*(\d+)", re.IGNORECASE)

_HP_THRESHOLD = 0.40  # hint when HP ≤ 40%


@dataclass
class PlayerVitals:
    is_thirsty: bool = False
    is_hungry: bool = False
    hp_current: int | None = None
    hp_max: int | None = None

    @property
    def hp_fraction(self) -> float | None:
        if self.hp_current is None or self.hp_max is None or self.hp_max == 0:
            return None
        return self.hp_current / self.hp_max


class VitalsTracker:
    def __init__(self) -> None:
        self._vitals = PlayerVitals()

    def update(self, response: str) -> None:
        if _THIRSTY_CLEAR.search(response):
            self._vitals.is_thirsty = False
        elif _THIRSTY_SET.search(response):
            self._vitals.is_thirsty = True

        if _HUNGRY_CLEAR.search(response):
            self._vitals.is_hungry = False
        elif _HUNGRY_SET.search(response):
            self._vitals.is_hungry = True

        m = _HP_RE.search(response)
        if m:
            self._vitals.hp_current = int(m.group(1))
            self._vitals.hp_max = int(m.group(2))

    @property
    def hint(self) -> str | None:
        frac = self._vitals.hp_fraction
        if frac is not None and frac <= _HP_THRESHOLD:
            pct = round(frac * 100)
            return f"[vitals] Low HP ({pct}%) — find a room with can_rest capability and rest"
        if self._vitals.is_thirsty:
            return "[vitals] You are thirsty — find a room with can_drink capability"
        if self._vitals.is_hungry:
            return "[vitals] You are hungry — find a room with can_eat capability"
        return None
