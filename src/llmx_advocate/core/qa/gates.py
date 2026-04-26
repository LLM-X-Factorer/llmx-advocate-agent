from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from llmx_advocate.core.models import PhaseId, QAGate

GateFn = Callable[[dict, dict[str, Any]], Awaitable[QAGate]]


@dataclass(frozen=True)
class Gate:
    gate_id: str
    name: str
    phase_id: PhaseId
    kind: str  # "rule" | "judge" | "rule+judge"
    optional: bool = False
    fn: GateFn | None = None


class GateRegistry:
    def __init__(self) -> None:
        self._gates: dict[str, Gate] = {}

    def register(self, gate: Gate) -> Gate:
        if gate.gate_id in self._gates:
            raise ValueError(f"Gate already registered: {gate.gate_id}")
        self._gates[gate.gate_id] = gate
        return gate

    def for_phase(self, phase_id: PhaseId, *, include_optional: bool = False) -> list[Gate]:
        return [
            g
            for g in self._gates.values()
            if g.phase_id == phase_id and (include_optional or not g.optional)
        ]

    def get(self, gate_id: str) -> Gate:
        return self._gates[gate_id]


registry = GateRegistry()
