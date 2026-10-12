"""Card colours: each Lane has a base hue, darkest at the top and fading towards the bottom."""

from PySide6.QtGui import QColor

from unlimilist.domain import LaneKind, Stage, Urgency

# Hue (0-359) per Lane; None means a cool grey.
_LANE_HUES: dict[tuple[Stage, LaneKind | None], int | None] = {
    (Stage.INBOX, LaneKind.SOMEDAY): 214,
    (Stage.INBOX, LaneKind.TIME_LIMITED): 174,
    (Stage.IN_PROCESS, LaneKind.SOMEDAY): 258,
    (Stage.IN_PROCESS, LaneKind.TIME_LIMITED): 140,
    (Stage.DONE, None): None,
}

URGENCY_COLOURS = {
    Urgency.OVERDUE: QColor("#E53935"),
    Urgency.DUE_SOON: QColor("#FFB300"),
}


def card_fill(stage: Stage, kind: LaneKind | None, index: int, count: int) -> QColor:
    """Fill colour for the card at `index` (0 = top) of a Lane holding `count` cards."""
    hue = _LANE_HUES[(stage, None if stage == Stage.DONE else kind)]
    fade = index / (count - 1) if count > 1 else 0.0
    lightness = 0.40 + 0.45 * fade
    if hue is None:
        return QColor.fromHslF(220 / 360, 0.10, lightness)
    return QColor.fromHslF(hue / 360, 0.62 - 0.22 * fade, lightness)


def text_colour(fill: QColor) -> QColor:
    """Black or white, whichever reads better on `fill`."""
    luminance = 0.2126 * fill.redF() + 0.7152 * fill.greenF() + 0.0722 * fill.blueF()
    return QColor("#1B1B1F") if luminance > 0.55 else QColor("#FFFFFF")
