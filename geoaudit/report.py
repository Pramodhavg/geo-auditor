"""Render an AuditResult to a single self-contained HTML file."""
from __future__ import annotations

import os

from jinja2 import Environment, FileSystemLoader

from .models import AuditResult

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")

STATUS_LABEL = {"pass": "Good", "warn": "Needs work", "fail": "Broken", "info": "Note"}


def _band(score: int) -> tuple[str, str]:
    if score >= 70:
        return "healthy", "Visible, with room to grow"
    if score >= 40:
        return "at-risk", "At risk — real gaps in AI visibility"
    return "critical", "Critical — largely invisible to AI search"


def _effort_label(n: int) -> str:
    return {1: "Easy", 2: "Moderate", 3: "Involved"}.get(n, "—")


def _impact_label(n: int) -> str:
    return {1: "Low", 2: "Medium", 3: "High"}.get(n, "—")


def render_report(result: AuditResult, out_path: str) -> str:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=True,
    )
    band_class, band_text = _band(result.total_score)
    tpl = env.get_template("report.html.j2")
    out = tpl.render(
        r=result,
        band_class=band_class,
        band_text=band_text,
        status_label=STATUS_LABEL,
        effort_label=_effort_label,
        impact_label=_impact_label,
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(out)
    return out_path
