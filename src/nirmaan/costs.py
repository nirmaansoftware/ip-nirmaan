"""What a project's model calls cost (M31): a view over the recorded ``ModelCall``s.

Tokens and cost are added up as recorded. A call whose provider reported no
usage, or whose model has no known price, counts as a call of unknown cost,
never as free.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from nirmaan.models import ModelCall, ProjectState


@dataclass
class CostLine:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    unknown_cost_calls: int = 0

    def add(self, call: ModelCall) -> None:
        self.calls += 1
        self.input_tokens += call.input_tokens or 0
        self.output_tokens += call.output_tokens or 0
        if call.cost_usd is None:
            self.unknown_cost_calls += 1
        else:
            self.cost_usd = round(self.cost_usd + call.cost_usd, 6)


@dataclass
class CostReport(CostLine):
    by_model: dict[str, CostLine] = field(default_factory=dict)
    by_purpose: dict[str, CostLine] = field(default_factory=dict)
    by_task: dict[str, CostLine] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def calls_cost(calls: Iterable[ModelCall]) -> CostReport:
    report = CostReport()
    for call in sorted(calls, key=lambda c: c.id):
        report.add(call)
        for table, key in ((report.by_model, call.model or "unknown"), (report.by_purpose, call.purpose),
                           (report.by_task, call.task)):
            table.setdefault(key, CostLine()).add(call)
    return report


def cost_report(state: ProjectState) -> CostReport:
    return calls_cost(state.model_calls.values())
