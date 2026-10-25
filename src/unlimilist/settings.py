"""The user's settings, kept in settings.json in the app-data folder, beside the tasks folder."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from unlimilist.domain import StaleLimits

CARD_FONT_SIZES = (1, 2, 3, 4, 5)
DEFAULT_CARD_FONT_SIZE = 2  # the size cards were drawn at before there was a choice
STALE_DAYS = range(1, 366)  # how many days a Stage may allow, on the Governance tab


@dataclass(frozen=True)
class Settings:
    card_font_size: int = DEFAULT_CARD_FONT_SIZE
    mark_stale: bool = True
    stale_inbox_days: int = StaleLimits().inbox
    stale_in_process_days: int = StaleLimits().in_process

    @property
    def stale_limits(self) -> StaleLimits | None:
        """The days each Stage allows before a Task is Stale, or None while Stale marking is off."""
        if not self.mark_stale:
            return None
        return StaleLimits(inbox=self.stale_inbox_days, in_process=self.stale_in_process_days)


class SettingsStore:
    def __init__(self, path: Path):
        self._path = path

    def load(self) -> Settings:
        """The saved settings. A missing, unreadable or odd file gives the defaults."""
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return Settings()
        if not isinstance(data, dict):
            return Settings()
        defaults = Settings()
        mark_stale = data.get("mark_stale")
        return Settings(
            card_font_size=_number(data.get("card_font_size"), CARD_FONT_SIZES, defaults.card_font_size),
            mark_stale=mark_stale if isinstance(mark_stale, bool) else defaults.mark_stale,
            stale_inbox_days=_number(data.get("stale_inbox_days"), STALE_DAYS, defaults.stale_inbox_days),
            stale_in_process_days=_number(
                data.get("stale_in_process_days"), STALE_DAYS, defaults.stale_in_process_days
            ),
        )

    def save(self, settings: Settings) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(asdict(settings), indent=2) + "\n", encoding="utf-8")


def _number(value, allowed, default: int) -> int:
    """`value` if it is one of `allowed`, otherwise `default`. true == 1, but it is no number."""
    if isinstance(value, bool) or not isinstance(value, int) or value not in allowed:
        return default
    return value
