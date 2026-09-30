from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


def display_value(value: Any) -> str:
    if isinstance(value, SymbolicValue):
        return value.render()
    if value is None:
        return "unbekannt"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


@dataclass(frozen=True)
class SourceRef:
    graph: str
    node_id: str
    port: str | None = None

    def render(self) -> str:
        return f"{self.node_id}.{self.port}" if self.port else self.node_id


@dataclass(frozen=True)
class SymbolicValue:
    kind: str
    value: Any = None
    resource_type: str | None = None
    resource_id: str | None = None
    amount: Any = None
    source: SourceRef | None = None
    complete: bool = True
    reason: str | None = None

    def render(self) -> str:
        if self.kind == "smart_res":
            return f"{self.resource_type or '?'} {self.resource_id or '?'} x{display_value(self.amount)}"
        if self.kind == "answer":
            return "AnswerData"
        if self.kind == "literal":
            return display_value(self.value)
        return f"ungelöst ({self.reason or self.kind})"


@dataclass(frozen=True)
class AnswerValue:
    lock: SymbolicValue | None
    price: SymbolicValue | None
    reward: SymbolicValue | None
    source: SourceRef
    complete: bool = True


@dataclass(frozen=True)
class Node:
    id: str
    type_name: str
    raw_type: str
    inputs: dict[str, Any]
    raw: dict[str, Any]


@dataclass(frozen=True)
class Edge:
    source: str
    source_port: str
    target: str
    target_port: str
    raw_type: str
    kind: Literal["flow", "data"]

    @property
    def key(self) -> tuple[str, str, str, str, str]:
        return self.source, self.source_port, self.target, self.target_port, self.raw_type


@dataclass
class Graph:
    name: str
    path: Path
    nodes: dict[str, Node]
    edges: list[Edge]
    diagnostics: list[str] = field(default_factory=list)
    duplicate_edges: int = 0
    incoming_flow: dict[str, list[Edge]] = field(default_factory=dict)
    outgoing_flow: dict[str, list[Edge]] = field(default_factory=dict)
    incoming_data: dict[tuple[str, str], list[Edge]] = field(default_factory=dict)
    outgoing_data: dict[tuple[str, str], list[Edge]] = field(default_factory=dict)


@dataclass(frozen=True)
class DialogueOption:
    multi_answer_node: str
    index: int
    phrase: str | None
    input_port: str | None
    output_port: str
    answer: AnswerValue | None
    target_nodes: tuple[str, ...]
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class Condition:
    text: str
    source: SourceRef


@dataclass(frozen=True)
class Effect:
    text: str
    source: SourceRef


@dataclass
class PathAlternative:
    entry: str
    node_ids: list[str] = field(default_factory=list)
    conditions: list[Condition] = field(default_factory=list)
    costs: list[str] = field(default_factory=list)
    effects: list[Effect] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    incomplete_reasons: list[str] = field(default_factory=list)


@dataclass
class RewardFinding:
    graph: str
    node_id: str
    kind: Literal["item", "relation"]
    resource_id: str | None
    amount: Any
    npc_id: str | None = None
    resource_detail: str | None = None
    option: DialogueOption | None = None
    paths: list[PathAlternative] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    apworld_suggestions: list[str] = field(default_factory=list)

    @property
    def reference(self) -> str:
        suffix = f"-option-{self.option.index}" if self.option else ""
        return f"{self.graph}:{self.node_id}{suffix}"

    @property
    def status(self) -> str:
        if not self.paths:
            return "keinem Einstieg zugeordnet"
        if self.issues or any(path.incomplete_reasons for path in self.paths):
            return "teilweise analysiert"
        return "vollständig analysiert"


@dataclass
class GraphAnalysis:
    graph: Graph
    findings: list[RewardFinding]
    options: list[DialogueOption]
    unsupported_types: set[str] = field(default_factory=set)
    limits_hit: list[str] = field(default_factory=list)
