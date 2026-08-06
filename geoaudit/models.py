"""Shared data structures. Everything the report renders flows through these."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Status = Literal["pass", "warn", "fail", "info"]


@dataclass
class Finding:
    id: str
    title: str
    status: Status
    # Evidence is mandatory in spirit: every finding must show proof.
    evidence: str
    why_it_matters: str  # plain-English, for a business owner
    fix: str = ""             # what to do
    fix_code: str = ""        # copy-pasteable snippet, when applicable
    impact: int = 2           # 1..3 (3 = high)
    effort: int = 2           # 1..3 (1 = easy)

    @property
    def priority_score(self) -> float:
        # Higher = do sooner. High impact, low effort floats to the top.
        return self.impact / self.effort


@dataclass
class CheckResult:
    key: str
    label: str
    score: float          # 0..1 within this check
    weight: float         # contribution to the 0..100 total
    findings: list[Finding] = field(default_factory=list)
    summary: str = ""

    @property
    def points(self) -> float:
        return round(self.score * self.weight, 1)


@dataclass
class ProbeRow:
    query: str
    appeared: bool
    answer_excerpt: str
    business_citations: list[str]
    competitor_domains: list[str]
    all_citations: list[str]
    error: str | None = None


@dataclass
class AuditResult:
    url: str
    domain: str
    business_name: str
    category_guess: str
    checks: list[CheckResult] = field(default_factory=list)
    probe_rows: list[ProbeRow] = field(default_factory=list)
    engine_name: str = ""
    generated_at: str = ""
    notes: list[str] = field(default_factory=list)  # honesty log: real vs modelled

    @property
    def total_score(self) -> int:
        return round(sum(c.points for c in self.checks))

    @property
    def all_findings(self) -> list[Finding]:
        out: list[Finding] = []
        for c in self.checks:
            out.extend(c.findings)
        return out

    @property
    def prioritized_fixes(self) -> list[Finding]:
        actionable = [f for f in self.all_findings if f.status in ("fail", "warn")]
        return sorted(actionable, key=lambda f: (-f.priority_score, -f.impact))
