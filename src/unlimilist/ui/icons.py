"""Line icons (Lucide style) rendered from inline SVG, crisp on Retina screens."""

from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QImageReader, QPixmap

from unlimilist.domain import Activity

_ASSETS = Path(__file__).resolve().parent.parent / "assets"
_APP_ICON = _ASSETS / "app_icon.png"

ACTIVITY_LABELS = {
    Activity.GENERAL_TASK: "General Task",
    Activity.PHONE_CALL: "Phone call",
    Activity.MEETING: "Meeting",
    Activity.DEVELOP_CODE: "Develop code",
    Activity.MILESTONE: "Milestone",
}

_PATHS = {
    "bold": '<path d="M6 12h9a4 4 0 0 1 0 8H7a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h7a4 4 0 0 1 0 8"/>',
    "italic": '<line x1="19" x2="10" y1="4" y2="4"/><line x1="14" x2="5" y1="20" y2="20"/>'
    '<line x1="15" x2="9" y1="4" y2="20"/>',
    "strikethrough": '<path d="M16 4H9a3 3 0 0 0-2.83 4"/><path d="M14 12a4 4 0 0 1 0 8H6"/>'
    '<line x1="4" x2="20" y1="12" y2="12"/>',
    "list": '<path d="M3 12h.01"/><path d="M3 18h.01"/><path d="M3 6h.01"/><path d="M8 12h13"/>'
    '<path d="M8 18h13"/><path d="M8 6h13"/>',
    "list-ordered": '<path d="M10 12h11"/><path d="M10 18h11"/><path d="M10 6h11"/><path d="M4 10h2"/>'
    '<path d="M4 6h1v4"/><path d="M6 18H4c0-1 2-2 2-3s-1-1.5-2-1"/>',
    "list-todo": '<rect x="3" y="5" width="6" height="6" rx="1"/><path d="m3 17 2 2 4-4"/><path d="M13 6h8"/>'
    '<path d="M13 12h8"/><path d="M13 18h8"/>',
    "code": '<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>'
    '<path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    "calendar": '<rect width="18" height="18" x="3" y="4" rx="2"/><path d="M16 2v4"/><path d="M8 2v4"/>'
    '<path d="M3 10h18"/>',
    "x": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "trash": '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/>'
    '<path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>',
    "lock": '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "minus": '<path d="M5 12h14"/>',
    "plus": '<path d="M5 12h14"/><path d="M12 5v14"/>',
}

_SCALE = 2  # render at 2x for Retina


def pixmap(name: str, colour: str = "#3A3D45", size: int = 18, stroke: float = 2.0) -> QPixmap:
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size * _SCALE}" height="{size * _SCALE}" '
        f'viewBox="0 0 24 24" fill="none" stroke="{colour}" stroke-width="{stroke}" '
        f'stroke-linecap="round" stroke-linejoin="round">{_PATHS[name]}</svg>'
    )
    image = QPixmap()
    image.loadFromData(svg.encode(), "SVG")
    image.setDevicePixelRatio(_SCALE)
    return image


def icon(name: str, colour: str = "#3A3D45", size: int = 18, disabled_colour: str = "#B8BBC3") -> QIcon:
    result = QIcon(pixmap(name, colour, size))
    result.addPixmap(pixmap(name, disabled_colour, size), QIcon.Mode.Disabled)
    return result


def app_icon() -> QIcon:
    """The Unlimilist app icon, for the window and the Dock."""
    return QIcon(str(_APP_ICON))


def activity_pixmap(activity: Activity, size: int) -> QPixmap:
    """The Activity's badge, rendered from its SVG at `size` points (crisp on Retina)."""
    reader = QImageReader(str(_ASSETS / "activity" / f"{activity.value}.svg"))
    reader.setScaledSize(QSize(size * _SCALE, size * _SCALE))
    image = QPixmap.fromImage(reader.read())
    image.setDevicePixelRatio(_SCALE)
    return image
