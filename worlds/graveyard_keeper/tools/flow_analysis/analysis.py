from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .model import (Condition, DialogueOption, Effect, Graph, GraphAnalysis, PathAlternative,
                    RewardFinding, SourceRef, SymbolicValue, display_value)
from .parser import unwrap_content
from .values import ValueResolver, extract_options


@dataclass(frozen=True)
class AnalysisLimits:
    max_paths: int = 32
    max_depth: int = 200
    max_states: int = 10_000


ENTRY_TYPES = {
    "CustomEvent", "CustomFunctionEvent", "Flow_CustomFunctionEvent", "OnEnable", "OnStart",
    "Flow_OnInteract", "Flow_OnEvent", "Flow_OnTrigger",
}

PASS_THROUGH_TYPES = {
    "Flow_Talk", "Wait", "Flow_WaitForFlow", "Flow_PlayerEnable", "Flow_DisablePlayerAnimation",
    "Flow_SetCharacterDirection", "Flow_FindWGO", "Flow_GetPlayer", "Flow_Vendor", "Dummy", "Return",
    "Flow_AddInteractionEvent", "Flow_AddPhraseToBlacklist", "Flow_UnlockPhrase", "Flow_RevealCrafth",
    "Flow_RemoveNPCToStock", "Flow_RunScript", "Flow_TriggerSinShardCharge", "Flow_MultiAnswer",
    "CustomEvent", "CustomFunctionEvent", "Flow_CustomFunctionEvent", "CustomFunctionCall",
    "MacroNodeWrapper", "Flow_Answer", "Flow_SmartRes", "OwnerVariable", "Flow_GetWGOParam",
    "IntegerAdd", "IntegerGreaterEqualThan", "SwitchBool",
    "Split", "Flow_GoTo",
}

CONDITION_TYPES = {
    "Flow_ParamFlag", "Flow_PlayerFlag", "Flow_ParamCompare", "Flow_CompareRelation", "Flow_CheckKeyQuest",
    "Flow_HasItem", "Flow_HasItemInInventory", "Flow_CheckItem", "Flow_CheckPhrase", "Flow_CheckDLC", "SwitchBool",
    "IntegerGreaterEqualThan", "Flow_PlayerParamCompare", "Flow_PlayerParamCompareInt",
    "Flow_RendomFlow",
}

EFFECT_TYPES = {
    "Flow_SetPlayerParam", "Flow_AddPlayerParam", "Flow_SetWGOParam", "Flow_AddWGOParam",
    "Flow_SetTaskState", "Flow_AddRelation", "Flow_DropItem", "Flow_RemoveItemFromInventory",
}


def _usable_smart_res(value: SymbolicValue | None) -> bool:
    return bool(
        value
        and value.kind == "smart_res"
        and value.resource_type
        and value.resource_id
        and value.amount is not None
        and not isinstance(value.amount, (dict, list))
    )


def _literal(raw: Any) -> Any:
    value = unwrap_content(raw)
    return value if not isinstance(value, (dict, list)) else None


def _first_input(node: Any, names: Iterable[str]) -> Any:
    lowered = {key.lower(): value for key, value in node.inputs.items()}
    for name in names:
        if name.lower() in lowered:
            return _literal(lowered[name.lower()])
    return None


def _resolved_scalar(resolver: ValueResolver, node_id: str, port_names: Iterable[str]) -> Any:
    node = resolver.graph.nodes[node_id]
    for port in port_names:
        if port in node.inputs or (node_id, port) in resolver.graph.incoming_data:
            value = resolver.resolve_input(node_id, port)
            if value is None:
                continue
            if isinstance(value, SymbolicValue):
                if value.kind == "literal":
                    return value.value
                return value
            return value
    return None


def _entry_label(graph: Graph, node_id: str) -> str:
    node = graph.nodes[node_id]
    event = node.raw.get("eventName")
    event_name = event.get("_value") if isinstance(event, dict) else None
    identifier = node.raw.get("identifier") or node.raw.get("_UID")
    suffix = event_name or identifier
    return f"{node.type_name} {node.id}" + (f" ({suffix})" if suffix else "")


def _inventory_requirement(resolver: ValueResolver, node_id: str) -> tuple[str | None, Any]:
    item = resolver.resolve_input(node_id, "Item")
    if isinstance(item, SymbolicValue) and item.kind == "item":
        amount = item.amount if isinstance(item.amount, (int, float)) and item.amount > 0 else 1
        return item.resource_id, amount
    item_id = _resolved_scalar(resolver, node_id, ("Item ID", "Res_id"))
    if isinstance(item_id, str) and item_id:
        return item_id, 1
    return None, 1


def _condition_for_edge(graph: Graph, edge: Any, resolver: ValueResolver) -> Condition | None:
    node = graph.nodes[edge.source]
    if node.type_name not in CONDITION_TYPES:
        return None
    if node.type_name == "Flow_HasItemInInventory":
        item_id, amount = _inventory_requirement(resolver, node.id)
        item = item_id or "<dynamisch/unaufgelöst>"
        branch = edge.source_port.strip().casefold()
        if branch == "yes":
            text = f"Item {item} x{display_value(amount)} im Inventar erforderlich"
        elif branch == "no":
            # Inventory can be rearranged freely. For progression analysis the
            # No branch therefore has no persistent requirement.
            return None
        else:
            text = (f"Flow_HasItemInInventory Item {item} x{display_value(amount)} "
                    f"-> {edge.source_port or '(default)'}")
        return Condition(text, SourceRef(graph.name, node.id, edge.source_port))
    if node.type_name == "Flow_RendomFlow":
        chance = _first_input(node, ("chance", "Chance"))
        chance_text = (f"{display_value(chance * 100)}%" if isinstance(chance, (int, float))
                       else "unbekannte Chance")
        text = f"Zufallsausgang {edge.source_port or '(default)'} ({chance_text} für true)"
        return Condition(text, SourceRef(graph.name, node.id, edge.source_port))
    subject = _first_input(node, ("param", "Param name", "npc_id", "Task", "Phrase", "DLC", "Res_id", "Item"))
    value = _first_input(node, ("Value", "value", "Amount", "amount"))
    if node.type_name in {"Flow_PlayerParamCompare", "Flow_PlayerParamCompareInt"}:
        text = (f"{node.type_name} {display_value(subject)} "
                f"{edge.source_port or '(default)'} {display_value(value)}")
        return Condition(text, SourceRef(graph.name, node.id, edge.source_port))
    details = " ".join(str(part) for part in (subject, value) if part is not None)
    text = f"{node.type_name} {details} -> {edge.source_port or '(default)'}".strip()
    return Condition(text, SourceRef(graph.name, node.id, edge.source_port))


def _comparison_result(value: Any, port: str, threshold: Any = None) -> bool | None:
    if not isinstance(value, (int, float, bool)):
        return None
    normalized = port.replace(" ", "")
    for operator in (">=", "<=", "!=", "==", ">", "<"):
        if normalized.startswith(operator):
            expected = threshold
            if normalized[len(operator):]:
                try:
                    expected = float(normalized[len(operator):])
                except ValueError:
                    return None
            if not isinstance(expected, (int, float, bool)):
                return None
            actual = float(value)
            expected_number = float(expected)
            return {">=": actual >= expected_number, "<=": actual <= expected_number,
                    "!=": actual != expected_number, "==": actual == expected_number,
                    ">": actual > expected_number, "<": actual < expected_number}[operator]
    return None


def _apply_state(node: Any, state: dict[tuple[str, str], Any]) -> None:
    if node.type_name == "Flow_SetPlayerParam":
        subject = _first_input(node, ("Param name", "param"))
        value = _first_input(node, ("Value", "value"))
        if subject is not None and value is not None:
            state[("player_param", str(subject))] = value
    elif node.type_name == "Flow_AddPlayerParam":
        subject = _first_input(node, ("Param name", "param"))
        delta = _first_input(node, ("Value", "value"))
        key = ("player_param", str(subject))
        if subject is not None and isinstance(delta, (int, float)) and isinstance(state.get(key, 0), (int, float)):
            state[key] = state.get(key, 0) + delta
    elif node.type_name == "Flow_AddRelation":
        npc = _first_input(node, ("npc_id", "NPC id"))
        delta = _first_input(node, ("Value", "value"))
        key = ("relation_delta", str(npc) if npc is not None else "<implicit>")
        if isinstance(delta, (int, float)):
            state[key] = state.get(key, 0) + delta
    elif node.type_name == "Flow_DropItem":
        item = _first_input(node, ("Res_id", "Item ID"))
        amount = _first_input(node, ("Amount", "Items Count"))
        if item is not None and isinstance(amount, (int, float)):
            key = ("inventory_delta", str(item))
            state[key] = state.get(key, 0) + amount
    elif node.type_name == "Flow_RemoveItemFromInventory":
        item = _first_input(node, ("Item ID", "Res_id"))
        amount = _first_input(node, ("Items Count", "Amount"))
        if item is not None and isinstance(amount, (int, float)):
            key = ("inventory_delta", str(item))
            state[key] = state.get(key, 0) - amount


def _state_aware_condition(graph: Graph, edge: Any, state: dict[tuple[str, str], Any],
                           resolver: ValueResolver
                           ) -> tuple[Condition | None, bool | None]:
    node = graph.nodes[edge.source]
    condition = _condition_for_edge(graph, edge, resolver)
    if condition is None:
        return None, None
    if node.type_name in {
        "Flow_ParamFlag", "Flow_PlayerFlag", "Flow_ParamCompare",
        "Flow_PlayerParamCompare", "Flow_PlayerParamCompareInt",
    }:
        subject = _first_input(node, ("param", "Param name"))
        known = state.get(("player_param", str(subject)))
        threshold = (_first_input(node, ("value", "Value"))
                     if node.type_name in {"Flow_PlayerParamCompare", "Flow_PlayerParamCompareInt"}
                     else None)
        result = _comparison_result(known, edge.source_port, threshold)
        return condition, result
    if node.type_name == "Flow_RendomFlow":
        chance = _first_input(node, ("chance", "Chance"))
        branch = edge.source_port.strip().casefold()
        if isinstance(chance, (int, float)):
            if branch == "true":
                return condition, False if chance <= 0 else (True if chance >= 1 else None)
            if branch == "false":
                return condition, False if chance >= 1 else (True if chance <= 0 else None)
        return condition, None
    if node.type_name == "Flow_CompareRelation":
        npc = _first_input(node, ("npc_id", "NPC id"))
        threshold = _first_input(node, ("Value", "value"))
        delta = state.get(("relation_delta", str(npc) if npc is not None else "<implicit>"), 0)
        if isinstance(threshold, (int, float)) and isinstance(delta, (int, float)) and delta:
            adjusted = threshold - delta
            text = (f"Flow_CompareRelation {npc if npc is not None else '<implizit>'}: "
                    f"Einstiegswert {edge.source_port} {display_value(adjusted)} "
                    f"(nach pfadinternem Delta {delta:+g})")
            return Condition(text, condition.source), None
    return condition, None


def _effect_for_node(graph: Graph, node_id: str) -> Effect | None:
    node = graph.nodes[node_id]
    if node.type_name not in EFFECT_TYPES:
        return None
    values: list[str] = []
    for key in ("Param name", "param", "Task", "State", "NPC id", "npc_id", "Res_id", "Amount", "Value",
                "Phrase", "Item ID", "Items Count"):
        if key in node.inputs:
            value = _literal(node.inputs[key])
            if value is not None:
                values.append(f"{key}={display_value(value)}")
    return Effect(f"{node.type_name}" + (": " + ", ".join(values) if values else ""),
                  SourceRef(graph.name, node_id))


def _known_type(node_type: str) -> bool:
    return node_type in PASS_THROUGH_TYPES or node_type in CONDITION_TYPES or node_type in EFFECT_TYPES


def _backward_paths(graph: Graph, target: str, limits: AnalysisLimits,
                    resolver: ValueResolver,
                    required_option: DialogueOption | None = None,
                    options_by_edge: dict[tuple[str, str], DialogueOption] | None = None
                    ) -> tuple[list[PathAlternative], list[str]]:
    results: list[PathAlternative] = []
    limit_messages: list[str] = []
    states = 0

    # (current node, reverse nodes, reverse edges, visited, incompleteness)
    stack: list[tuple[str, list[str], list[Any], frozenset[str], list[str]]] = [
        (target, [target], [], frozenset({target}), [])
    ]
    while stack:
        current, reverse_nodes, reverse_edges, visited, incomplete = stack.pop()
        states += 1
        if states > limits.max_states:
            limit_messages.append(f"state limit {limits.max_states} reached at target {target}")
            break
        incoming = graph.incoming_flow[current]
        node = graph.nodes[current]
        is_function_entry = node.type_name in {"CustomFunctionEvent", "Flow_CustomFunctionEvent"}
        is_entry = (node.type_name in ENTRY_TYPES and not is_function_entry) or not incoming
        if is_entry:
            if required_option and not any(
                edge.source == required_option.multi_answer_node and edge.source_port == required_option.output_port
                for edge in reverse_edges
            ):
                continue
            forward_nodes = list(reversed(reverse_nodes))
            forward_edges = list(reversed(reverse_edges))
            alternative = PathAlternative(_entry_label(graph, current))
            alternative.node_ids = forward_nodes
            alternative.incomplete_reasons.extend(incomplete)
            for path_node in forward_nodes:
                effect = _effect_for_node(graph, path_node)
                if effect:
                    alternative.effects.append(effect)
                candidate = graph.nodes[path_node]
                if not _known_type(candidate.type_name) and len(graph.outgoing_flow[path_node]) > 1:
                    alternative.incomplete_reasons.append(
                        f"unbekannter verzweigender Node-Typ {candidate.type_name} bei Node {path_node}"
                    )
                if candidate.type_name == "Flow_RemoveItemFromInventory":
                    item = _first_input(candidate, ("Item ID", "Res_id"))
                    amount = _first_input(candidate, ("Items Count", "Amount"))
                    alternative.conditions.append(Condition(
                        f"Item {display_value(item)} x{display_value(amount)} erforderlich",
                        SourceRef(graph.name, candidate.id),
                    ))
            state: dict[tuple[str, str], Any] = {}
            impossible = False
            for edge in forward_edges:
                _apply_state(graph.nodes[edge.source], state)
                condition, result = _state_aware_condition(graph, edge, state, resolver)
                if result is True and condition:
                    alternative.effects.append(Effect(
                        f"Pfadinterner Zustand erfüllt Prüfung: {condition.text}", condition.source
                    ))
                elif result is False:
                    impossible = True
                    break
                elif condition:
                    alternative.conditions.append(condition)
                alternative.evidence.append(
                    f"{edge.source}.{edge.source_port or '(default)'} -> {edge.target}.{edge.target_port or '(default)'}"
                )
                if edge.raw_type == "Synthetic.CustomFunctionCall":
                    alternative.incomplete_reasons.append(
                        "lokaler Funktionsaufruf per UID verbunden; Rückkehr und Parameter sind nicht interpretiert"
                    )
                option = (options_by_edge or {}).get((edge.source, edge.source_port))
                if option:
                    for answer in option.answers:
                        if _usable_smart_res(answer.lock):
                            alternative.conditions.append(Condition(
                                f"Optionssperre: {answer.lock.render()}",
                                answer.lock.source or answer.source,
                            ))
                        if _usable_smart_res(answer.price):
                            if answer.price.resource_type == "Item":
                                alternative.conditions.append(Condition(
                                    f"Item {answer.price.resource_id} "
                                    f"x{display_value(answer.price.amount)} erforderlich",
                                    answer.price.source or answer.source,
                                ))
                            else:
                                alternative.costs.append(
                                    f"{answer.price.render()} (Optionskosten)"
                                )
                        option_reward = answer.reward
                        if _usable_smart_res(option_reward):
                            alternative.effects.append(Effect(
                                f"Optionsbelohnung: {option_reward.render()}",
                                option_reward.source or answer.source,
                            ))
                            if option_reward.resource_id == "_rel":
                                alternative.incomplete_reasons.append(
                                    f"Empfänger der Relationsbelohnung für Option {option.index} ist implizit"
                                )
            if impossible:
                continue
            results.append(alternative)
            if len(results) >= limits.max_paths:
                limit_messages.append(f"path limit {limits.max_paths} reached at target {target}")
                break
            continue
        if len(reverse_edges) >= limits.max_depth:
            limit_messages.append(f"depth limit {limits.max_depth} reached at target {target}")
            continue
        for edge in reversed(incoming):
            if edge.source in visited:
                # Menu/dialogue loops are common. Preserve the acyclic route and disclose the skipped loop.
                next_incomplete = incomplete + [f"Schleife über Node {edge.source} nicht erneut durchlaufen"]
                if graph.nodes[edge.source].type_name in ENTRY_TYPES:
                    stack.append((edge.source, reverse_nodes + [edge.source], reverse_edges + [edge], visited,
                                  next_incomplete))
                continue
            stack.append((edge.source, reverse_nodes + [edge.source], reverse_edges + [edge],
                          visited | {edge.source}, incomplete))
    # Deterministic de-duplication for paths converging through duplicated semantic routes.
    unique: dict[tuple[str, tuple[str, ...]], PathAlternative] = {}
    for path in results:
        unique.setdefault((path.entry, tuple(path.evidence)), path)
    return list(unique.values()), sorted(set(limit_messages))


def _is_positive(value: Any) -> bool:
    if isinstance(value, SymbolicValue):
        value = value.amount if value.kind == "smart_res" else value.value
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def _is_overhead_roundtrip_drop(graph: Graph, node_id: str) -> bool:
    """Whether a drop only transfers the player's displayed overhead item.

    Sermon setup reads the currently selected prayer with Flow_GetOverhead,
    passes that exact Item into Flow_DropItem, and immediately restores the
    overhead display.  This is presentation/inventory plumbing, not a newly
    awarded item.
    """
    item_sources = graph.incoming_data.get((node_id, "Item"), [])
    reads_overhead = any(
        graph.nodes[edge.source].type_name == "Flow_GetOverhead"
        for edge in item_sources
    )
    restores_overhead = any(
        graph.nodes[edge.target].type_name == "Flow_SetOverhead"
        for edge in graph.outgoing_flow[node_id]
    )
    return reads_overhead and restores_overhead


def _direct_findings(graph: Graph, resolver: ValueResolver) -> list[RewardFinding]:
    findings: list[RewardFinding] = []
    for node in graph.nodes.values():
        if node.type_name == "Flow_DropItem":
            if _is_overhead_roundtrip_drop(graph, node.id):
                continue
            item = resolver.resolve_input(node.id, "Item")
            if isinstance(item, SymbolicValue) and item.kind == "item" and item.resource_id is not None:
                resource, amount = item, item.amount
            else:
                resource = _resolved_scalar(resolver, node.id, ("Res_id", "res_id"))
                amount = _resolved_scalar(resolver, node.id, ("Amount", "amount", "Value"))
                if resource is None and isinstance(item, SymbolicValue) and item.kind == "item":
                    resource, amount = item, item.amount
            resource_id = resource.resource_id if isinstance(resource, SymbolicValue) else resource
            resource_detail = (resource.reason if isinstance(resource, SymbolicValue) else None)
            if resource_id is None and resource_detail is None:
                resource_detail = "no fixed item source found"
            if isinstance(amount, SymbolicValue) and amount.kind == "literal":
                amount = amount.value
            # Flow_DropItem.RegisterPorts sets the serialized default to 1. Unity
            # exports may omit that port entirely when the default is unchanged.
            if amount is None:
                amount = 1
            issues = []
            if resource_id is None:
                issues.append("Item-ID konnte nicht aufgelöst werden")
            findings.append(RewardFinding(graph.name, node.id, "item", resource_id, amount,
                                          resource_detail=resource_detail, issues=issues))
        elif node.type_name == "Flow_AddRelation":
            amount = _resolved_scalar(resolver, node.id, ("Value", "value"))
            npc = _resolved_scalar(resolver, node.id, ("npc_id", "NPC id"))
            if isinstance(amount, SymbolicValue) and amount.kind == "literal":
                amount = amount.value
            if not _is_positive(amount):
                continue
            issues = ["NPC-Kontext ist implizit und konnte nicht belegt werden"] if npc is None else []
            findings.append(RewardFinding(graph.name, node.id, "relation", "_rel", amount,
                                          npc_id=str(npc) if npc is not None else None, issues=issues))
    return findings


def _answer_findings(graph: Graph, options: list[DialogueOption]) -> list[RewardFinding]:
    findings: list[RewardFinding] = []
    for option in options:
        for answer in option.answers:
            reward = answer.reward
            if not reward or reward.kind != "smart_res" or reward.resource_id != "_rel" or not _is_positive(reward):
                continue
            node_id = answer.source.node_id
            issues = list(option.issues)
            issues.append("Empfänger von GameRes _rel ist aus AnswerData allein nicht belegt")
            findings.append(RewardFinding(graph.name, node_id, "relation", reward.resource_id, reward.amount,
                                          option=option, issues=issues))
    return findings


def analyze_graph(graph: Graph, limits: AnalysisLimits | None = None) -> GraphAnalysis:
    limits = limits or AnalysisLimits()
    resolver = ValueResolver(graph)
    options = extract_options(graph, resolver)
    options_by_edge = {(option.multi_answer_node, option.output_port): option for option in options}
    findings = _direct_findings(graph, resolver) + _answer_findings(graph, options)
    limits_hit: list[str] = []
    for finding in findings:
        targets = finding.option.target_nodes if finding.option and finding.option.target_nodes else (finding.node_id,)
        paths = []
        messages = []
        for target in targets:
            target_paths, target_messages = _backward_paths(
                graph, target, limits, resolver, finding.option, options_by_edge
            )
            paths.extend(target_paths)
            messages.extend(target_messages)
        limits_hit.extend(messages)
        finding.paths = paths
        finding.issues.extend(message for message in resolver.issues if message not in finding.issues)
        if messages:
            finding.issues.extend(messages)
    supported = PASS_THROUGH_TYPES | CONDITION_TYPES | EFFECT_TYPES
    unsupported = {node.type_name for node in graph.nodes.values() if node.type_name not in supported}
    findings.sort(key=lambda item: (item.node_id.zfill(12), item.option.index if item.option else -1, item.kind))
    return GraphAnalysis(graph, findings, options, unsupported, sorted(set(limits_hit)))
