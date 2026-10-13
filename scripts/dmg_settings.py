# dmgbuild settings for the Unlimilist installer; build_dmg.sh passes `app` and `icon` with -D.
# dmgbuild writes the Finder layout itself, so building needs no Finder automation permission.
# ruff: noqa: F821  (`defines` is provided by dmgbuild)

app = defines["app"]

format = "UDZO"
compression_level = 9
filesystem = "HFS+"
files = [app]
symlinks = {"Applications": "/Applications"}
icon = defines["icon"]  # the disk's own icon

default_view = "icon-view"
show_status_bar = False
show_tab_view = False
show_toolbar = False
show_pathbar = False
show_sidebar = False
window_rect = ((200, 120), (560, 340))
arrange_by = None
icon_size = 128
text_size = 13
icon_locations = {
    "Unlimilist.app": (140, 150),
    "Applications": (420, 150),
}
