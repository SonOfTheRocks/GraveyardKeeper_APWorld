from __future__ import annotations

import re
from typing import Any

from .model import AnswerValue, DialogueOption, Graph, SourceRef, SymbolicValue
from .parser import unwrap_content


_OPTION_INDEX = re.compile(r"#(\d+)")


def option_index(port: str) -> int | None:
    match = _OPTION_INDEX.search(port)
    return int(match.group(1)) if match else None


class ValueResolver:
    def __init__(self, graph: Graph):
        self.graph = graph
        self._cache: dict[tuple[str, str], SymbolicValue | AnswerValue | None] = {}
        self.issues: list[str] = []

    def resolve_input(self, node_id: str, port: str, stack: tuple[tuple[str, str], ...] = ()) -> Any:
        key = (node_id, port)
        if key in stack:
            return SymbolicValue("unresolved", source=SourceRef(self.graph.name, node_id, port), complete=False,
                                 reason="cyclic data dependency")
        edges = self.graph.incoming_data.get(key, [])
        if edges:
            if len(edges) > 1:
                self.issues.append(f"{node_id}.{port}: multiple connected data sources")
                return SymbolicValue("unresolved", source=SourceRef(self.graph.name, node_id, port), complete=False,
                                     reason="multiple connected data sources")
            edge = edges[0]
            return self.resolve_output(edge.source, edge.source_port, stack + (key,))
        node = self.graph.nodes[node_id]
        return self.resolve_raw(node.inputs.get(port), SourceRef(self.graph.name, node_id, port), stack + (key,))

    def resolve_output(self, node_id: str, port: str, stack: tuple[tuple[str, str], ...] = ()) -> Any:
        key = (node_id, port)
        if key in self._cache:
            return self._cache[key]
        node = self.graph.nodes[node_id]
        source = SourceRef(self.graph.name, node_id, port)
        if node.type_name == "Flow_SmartRes":
            # Older/exporter-specific wrappers use display labels for two ports
            # ("Id", "V") while newer dumps use the serialized field names.
            # Some old nodes contain both "Res type" and "res_type" with
            # conflicting values, so the canonical lowercase port wins.
            value = SymbolicValue(
                "smart_res",
                resource_type=self._literal(node.inputs.get(
                    "res_type", node.inputs.get("Res type"))),
                resource_id=self._literal(node.inputs.get(
                    "id", node.inputs.get("Id"))),
                amount=self._literal(node.inputs.get(
                    "v", node.inputs.get("V"))),
                source=source,
            )
        elif node.type_name == "Flow_CreateItem":
            resource_id = self._scalar(self.resolve_input(node_id, "item_id", stack))
            amount = self._scalar(self.resolve_input(node_id, "value", stack))
            value = SymbolicValue(
                "item", resource_type="Item", resource_id=resource_id, amount=amount, source=source,
                complete=resource_id is not None,
                reason=None if resource_id is not None else "Flow_CreateItem receives its item id dynamically",
            )
        elif node.type_name.startswith("Identity"):
            value = self.resolve_input(node_id, "value", stack)
        elif node.type_name == "Flow_GetWGOItemList":
            value = SymbolicValue("unresolved", source=source, complete=False,
                                  reason=f"dynamic output {node.type_name}.{port}")
        elif node.type_name == "Flow_Answer":
            lock = self._as_smart_res(self.resolve_input(node_id, "lock", stack), node_id, "lock")
            price = self._as_smart_res(self.resolve_input(node_id, "price", stack), node_id, "price")
            reward = self._as_smart_res(self.resolve_input(node_id, "reward", stack), node_id, "reward")
            complete = all(part is None or part.complete for part in (lock, price, reward))
            value = AnswerValue(lock, price, reward, source, complete)
        elif node.type_name == "Flow_AnswersArray":
            values: list[AnswerValue] = []
            ports = sorted(node.inputs, key=lambda name: option_index(name) if option_index(name) is not None else 10**9)
            for input_port in ports:
                resolved = self.resolve_input(node_id, input_port, stack)
                if isinstance(resolved, AnswerValue):
                    values.append(resolved)
            value = tuple(values)
        elif node.type_name == "Flow_MultipleAnswer":
            resolved = self.resolve_input(node_id, "datas", stack)
            if resolved is None:
                resolved = self.resolve_input(node_id, "datasArray", stack)
            values = list(resolved) if isinstance(resolved, tuple) else []
            reward = self._as_smart_res(self.resolve_input(node_id, "reward", stack), node_id, "reward")
            if reward is not None:
                values.append(AnswerValue(None, None, reward, source, reward.complete))
            value = tuple(values)
        elif len(node.inputs) == 1:
            input_name = next(iter(node.inputs))
            value = self.resolve_input(node_id, input_name, stack)
        else:
            value = SymbolicValue("unresolved", source=source, complete=False,
                                  reason=f"dynamic output {node.type_name}.{port}")
        self._cache[key] = value
        return value

    def resolve_raw(self, raw: Any, source: SourceRef, stack: tuple[tuple[str, str], ...] = ()) -> Any:
        if raw is None or raw == {}:
            return None
        if isinstance(raw, dict) and raw.get("$type") == "AnswerData":
            lock = self._as_smart_res(self.resolve_raw(raw.get("d_lock", raw.get("lock")), source, stack), source.node_id, "lock")
            price = self._as_smart_res(self.resolve_raw(raw.get("d_price", raw.get("price")), source, stack), source.node_id, "price")
            reward = self._as_smart_res(self.resolve_raw(raw.get("d_reward", raw.get("reward")), source, stack), source.node_id, "reward")
            return AnswerValue(lock, price, reward, source, all(v is None or v.complete for v in (lock, price, reward)))
        if isinstance(raw, dict) and raw.get("$type") == "SmartRes":
            return self._smart_res_from_raw(raw, source)
        if isinstance(raw, dict) and raw.get("$type") == "Item":
            resource_id = self._literal(raw.get("id"))
            amount = self._literal(raw.get("value"))
            return SymbolicValue(
                "item", resource_type="Item", resource_id=resource_id, amount=amount, source=source,
                complete=resource_id is not None,
                reason=None if resource_id is not None else "serialized Item has no fixed id",
            )
        content = unwrap_content(raw)
        if content is not raw:
            return SymbolicValue("literal", value=content, source=source)
        if isinstance(raw, (str, int, float, bool)):
            return SymbolicValue("literal", value=raw, source=source)
        return SymbolicValue("unresolved", source=source, complete=False, reason="serialized value has no usable content")

    @staticmethod
    def _literal(raw: Any) -> Any:
        value = unwrap_content(raw)
        return value if not isinstance(value, (dict, list)) else None

    @staticmethod
    def _scalar(value: Any) -> Any:
        if isinstance(value, SymbolicValue):
            if value.kind == "literal":
                return value.value
            return value.resource_id if value.resource_id is not None else value.value
        return value

    def _smart_res_from_raw(self, raw: dict[str, Any], source: SourceRef) -> SymbolicValue | None:
        if not raw or raw == {"$type": "SmartRes"}:
            return None
        resource_type = self._literal(raw.get("res_type") or raw.get("d_res_type"))
        resource_id = self._literal(raw.get("id") or raw.get("d_id"))
        amount = self._literal(raw.get("v") or raw.get("d_v"))
        item = raw.get("item")
        params = item.get("_params", {}) if isinstance(item, dict) else {}
        if resource_type is None and isinstance(params, dict):
            resource_type = self._first(params.get("_res_type"))
            amount = amount if amount is not None else self._first(params.get("_res_v"))
        if resource_type is None and resource_id is None and amount is None:
            return None
        return SymbolicValue("smart_res", resource_type=resource_type, resource_id=resource_id,
                             amount=amount, source=source, complete=resource_id is not None)

    @staticmethod
    def _first(value: Any) -> Any:
        if isinstance(value, list) and value:
            return unwrap_content(value[0])
        return unwrap_content(value)

    @staticmethod
    def _as_smart_res(value: Any, node_id: str, port: str) -> SymbolicValue | None:
        if value is None or isinstance(value, SymbolicValue):
            return value
        return SymbolicValue("unresolved", source=SourceRef("", node_id, port), complete=False,
                             reason="expected SmartRes")


def extract_options(graph: Graph, resolver: ValueResolver) -> list[DialogueOption]:
    options: list[DialogueOption] = []
    for node in graph.nodes.values():
        if node.type_name != "Flow_MultiAnswer":
            continue
        answers = node.raw.get("answers")
        answers = answers if isinstance(answers, list) else []
        ports: dict[int, str] = {}
        for port in node.inputs:
            index = option_index(port)
            if index is not None:
                ports[index] = port
        outgoing: dict[int, list[str]] = {}
        for edge in graph.outgoing_flow[node.id]:
            match = re.fullmatch(r"out_(\d+)", edge.source_port)
            if match:
                outgoing.setdefault(int(match.group(1)), []).append(edge.target)
        for index in sorted(set(range(len(answers))) | set(ports) | set(outgoing)):
            issues: list[str] = []
            port = ports.get(index)
            resolved_answer = resolver.resolve_input(node.id, port) if port else None
            additional_answers: tuple[AnswerValue, ...] = ()
            if isinstance(resolved_answer, tuple) and all(isinstance(value, AnswerValue) for value in resolved_answer):
                answer = resolved_answer[0] if resolved_answer else None
                additional_answers = tuple(resolved_answer[1:])
            else:
                answer = resolved_answer
            if answer is not None and not isinstance(answer, AnswerValue):
                issues.append("option input did not resolve to AnswerData")
                answer = None
            if index >= len(answers):
                issues.append("option port/output has no phrase entry")
            if not outgoing.get(index):
                issues.append("option has no connected control-flow output")
            options.append(DialogueOption(node.id, index, answers[index] if index < len(answers) else None,
                                          port, f"out_{index}", answer, tuple(outgoing.get(index, [])), tuple(issues),
                                          additional_answers))
    return options
