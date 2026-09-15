from appkit_ui.styles import sticky_header_style

TABLE_HEADER_STYLE = {
    **sticky_header_style,
    "backgroundColor": "var(--alloq-surface-solid)",
}

TABLE_STYLE = {
    "borderCollapse": "collapse",
    "borderSpacing": "0",
    "margin": "0",
    "width": "100%",
    "tableLayout": "fixed",
}

TABLE_WRAPPER_STYLE = {
    "backgroundColor": "var(--alloq-fade-bg)",
    "borderRadius": "var(--mantine-radius-sm)",
    "margin": "0",
    "overflowX": "auto",
    "overflowY": "hidden",
    "padding": "0",
}

NO_WRAP_CELL_STYLE = {
    "whiteSpace": "nowrap",
}
