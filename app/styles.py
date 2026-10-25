"""Styles for the app. Colors and spacing live in alloq_commons.theme."""

import reflex as rx
from alloq_commons import theme
from reflex.components.component import ComponentStyle

base_stylesheets = [
    "css/react-zoom.css",
    "css/appkit.css",
    "css/alloq-theme.css",
    "css/aq-shell.css",
    "css/aq-list.css",
    "css/aq-splash.css",
    "css/aq-toast.css",
    "css/aq-workshop.css",
    "css/aq-viewer.css",
]

base_style: ComponentStyle = {
    "font_family": theme.FONT_FAMILY,
    rx.icon: {
        "stroke_width": "1.5px",
    },
}
