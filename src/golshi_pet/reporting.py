"""Structured findings shared by validation, installation, and derby runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Severity = Literal["error", "warning", "info"]


@dataclass(frozen=True, slots=True)
class Finding:
    code: str
    severity: Severity
    message: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AuditReport:
    """A machine-readable report with stable finding codes."""

    subject: str
    findings: list[Finding] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not any(item.severity == "error" for item in self.findings)

    def add(
        self,
        code: str,
        severity: Severity,
        message: str,
        **context: Any,
    ) -> None:
        self.findings.append(Finding(code, severity, message, context))

    def extend(self, other: AuditReport) -> None:
        self.findings.extend(other.findings)
        self.metrics.update(other.metrics)

    def to_dict(self) -> dict[str, Any]:
        counts = {
            level: sum(item.severity == level for item in self.findings)
            for level in ("error", "warning", "info")
        }
        return {
            "ok": self.ok,
            "subject": self.subject,
            "counts": counts,
            "metrics": self.metrics,
            "findings": [asdict(item) for item in self.findings],
        }
