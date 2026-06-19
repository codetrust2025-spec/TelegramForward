"""Patch built CSS for daily-ops toolbar layout crush."""
from pathlib import Path

CSS = Path("static/assets/index-X8Z7CYT5.css")

css = CSS.read_text(encoding="utf-8")
orig = css

css = css.replace(
    ".ops-dash-toolbar--v3{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;",
    ".ops-dash-toolbar--v3{display:grid;grid-template-columns:minmax(11rem,auto) minmax(0,1fr);align-items:start;",
)
css = css.replace(
    ".ops-dash-toolbar__intro{min-width:0}",
    ".ops-dash-toolbar__intro{min-width:11rem;max-width:100%}",
)
css = css.replace(
    ".ops-dash-toolbar__actions{display:inline-flex;align-items:center;gap:8px;flex-shrink:0;padding-left:12px;border-left:1px solid rgba(255,255,255,.08)}",
    ".ops-dash-toolbar__actions{display:inline-flex;align-items:center;gap:8px;flex-shrink:1;flex-wrap:wrap;min-width:0;justify-content:flex-end;padding-left:12px;border-left:1px solid rgba(255,255,255,.08)}",
)
css = css.replace(
    ".ops-dash-toolbar--v3{flex-direction:column;align-items:stretch;gap:10px}",
    ".ops-dash-toolbar--v3{grid-template-columns:1fr;gap:10px}",
)
if ".ops-dash-toolbar__intro .ops-dash-title" not in css:
    css += (
        ".ops-dash-toolbar__intro .ops-dash-title,.ops-dash-toolbar__intro .ops-dash-sub{white-space:nowrap}"
        "@media (max-width:900px){.ops-dash-toolbar__actions{border-left:none;padding-left:0;justify-content:flex-start}"
        ".ops-dash-toolbar__intro .ops-dash-title,.ops-dash-toolbar__intro .ops-dash-sub{white-space:normal}}"
    )

if css == orig:
    raise SystemExit("no CSS changes applied")
CSS.write_text(css, encoding="utf-8")
print("patched", CSS)
