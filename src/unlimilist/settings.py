"""The user's settings, kept in settings.json in the app-data folder, beside the tasks folder."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

CARD_FONT_SIZES = (1, 2, 3, 4, 5)
DEFAULT_CARD_FONT_SIZE = 2  # the size cards were drawn at before there was a choice


@dataclass(frozen=True)
class Settings:
    card_font_size: int = DEFAULT_CARD_FONT_SIZE


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
        size = data.get("card_font_size")
        if isinstance(size, bool) or size not in CARD_FONT_SIZES:  # true == 1, but it is no size
            size = DEFAULT_CARD_FONT_SIZE
        return Settings(card_font_size=size)

    def save(self, settings: Settings) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(asdict(settings), indent=2) + "\n", encoding="utf-8")
