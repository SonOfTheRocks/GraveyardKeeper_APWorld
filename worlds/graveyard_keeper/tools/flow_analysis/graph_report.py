from __future__ import annotations

import html
import json
import re
from collections import deque
from pathlib import Path
from typing import Any

from .model import Edge, Graph, GraphAnalysis, Node, display_value
from .parser import unwrap_content
from .summaries import QuestSummary, build_phrase_unlock_index, build_quest_summaries


CONTENT_PACKS = ("Base Game", "Better Call Soul", "Game of Crone", "Stranger Sins")

# These scripts are shipped in the game data but expose developer-facing test
# interactions rather than player quest progression.  Keep them in the payload
# for diagnostics, while letting the HTML hide them by default.
DEBUG_GRAPH_NAMES = frozenset({"body_spawn", "priest_speak"})
DEBUG_NODE_REFERENCES = frozenset({
    # Detached duplicate of pray's live first-sermon branch.  It has no flow
    # entry in on_start_preaching and the real PrayCraftGUI path runs `pray`.
    "on_start_preaching:100",
    "on_start_preaching:102",
    "on_start_preaching:104",
})


def _is_debug_graph(graph_name: str) -> bool:
    normalized = graph_name.casefold()
    return normalized.startswith("test_") or normalized in DEBUG_GRAPH_NAMES


def _is_debug_node(graph_name: str, reference: str) -> bool:
    return _is_debug_graph(graph_name) or reference in DEBUG_NODE_REFERENCES


def load_quest_node_names(path: Path | None) -> dict[str, str]:
    """Load manually curated end-graph display names without affecting quest data."""
    if path is None or not path.is_file():
        return {}
    try:
        values = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(values, dict):
        return {}
    return {
        str(node_id): name.strip()
        for node_id, name in values.items()
        if isinstance(name, str) and name.strip()
    }


def build_game_data_script_index(game_data_dir: Path | None) -> dict[str, list[dict[str, Any]]]:
    """Index FlowGraph entry scripts referenced by exported vanilla GameData."""
    if game_data_dir is None or not game_data_dir.is_dir():
        return {}

    def script_values(value: Any) -> list[str]:
        if isinstance(value, str):
            return [value] if value and not value.startswith(":") else []
        if isinstance(value, list):
            return [entry for item in value for entry in script_values(item)]
        return []

    def script_fields(value: Any, prefix: tuple[str, ...] = ()) -> list[tuple[str, Any]]:
        result: list[tuple[str, Any]] = []
        if isinstance(value, dict):
            for key, child in value.items():
                path = prefix + (str(key),)
                if "script" in str(key).casefold():
                    result.append((".".join(path), child))
                else:
                    result.extend(script_fields(child, path))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                result.extend(script_fields(child, prefix + (str(index),)))
        return result

    index: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(game_data_dir.glob("*.json"), key=lambda item: item.name.casefold()):
        try:
            records = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(records, list):
            continue
        for record_index, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            record_id = str(record.get("id") or record_index)
            for field, value in script_fields(record):
                for script in script_values(value):
                    source: dict[str, Any] = {
                        "file": path.name, "record": record_id, "field": field,
                    }
                    if path.name == "quests_data.json":
                        source["trigger"] = ", ".join(map(str, record.get("start_key", []))) or "quest state"
                    elif path.name == "objs_data.json":
                        source["trigger"] = f"world object {record_id}"
                    elif path.name == "craft_data.json":
                        source["trigger"] = f"craft {record_id}"
                        source["requiredItems"] = [
                            f"{item.get('id')} x{display_value(item.get('value', 1))}"
                            for item in record.get("needs", []) if isinstance(item, dict) and item.get("id")
                        ]
                    elif path.name == "items_data.json":
                        source["trigger"] = f"item {record_id}"
                    elif path.name == "logics_data.json":
                        source["trigger"] = f"scheduled logic {record_id}"
                    elif path.name == "cutscenes_data.json":
                        source["trigger"] = f"item {record.get('item') or record_id}"
                    else:
                        source["trigger"] = record_id
                    if source not in index.setdefault(script, []):
                        index[script].append(source)
    return index


def _reward_dicts(summary: QuestSummary) -> list[dict[str, Any]]:
    rewards: list[dict[str, Any]] = []
    for reward in summary.relation_rewards:
        rewards.append({
            "type": "relation", "amount": display_value(reward.amount),
            "npc": reward.npc or "unresolved", "npcSource": reward.npc_source,
        })
    for reward in summary.item_drops:
        rewards.append({
            "type": "item_drop", "item": reward.item or "dynamic/unresolved",
            "amount": display_value(reward.amount), "resolution": reward.resolution,
        })
    return rewards


def _summary_data(summary: QuestSummary) -> dict[str, Any]:
    return {
        "id": summary.reference,
        "file": f"{summary.graph}.json",
        "graph": summary.graph,
        "multiAnswer": summary.multi_answer,
        "multiAnswerNode": summary.multi_answer_node,
        "multiAnswerNodes": [summary.multi_answer_node] if summary.multi_answer_node else [],
        "rewards": _reward_dicts(summary),
        "requiredQuests": summary.required_quests,
        "requiredQuestSources": summary.phrase_unlock_sources,
        "requiredHappiness": [{
            "amount": display_value(value.amount), "npc": value.npc or "unresolved",
            "npcSource": value.npc_source,
        } for value in summary.required_happiness],
        "requiredItems": summary.required_items,
        "costs": summary.costs,
        "otherRequirements": summary.other_requirements,
        "functionCalls": summary.function_calls,
        "conversations": summary.conversations,
        "taskStates": [{"task": value.task, "state": value.state} for value in summary.task_states],
        "phrasesToBlacklist": summary.phrases_to_blacklist,
        "phrasesRemovedFromBlacklist": summary.phrases_removed_from_blacklist,
        "phrasesUnlocked": summary.phrases_unlocked,
        "stateEventLinks": [],
        "playerStateChanges": [],
        "playerStateLinks": [],
        "scriptLinks": [],
        "eventLinks": [],
        "externalSources": [],
        "entryEvents": [],
        "choiceLinks": [],
        "choiceAlternatives": [],
        "returnsToChoiceMenu": False,
        "unresolvedEntry": False,
        "uncertainties": summary.uncertainties,
    }


def _input(node: Node, *names: str) -> Any:
    lowered = {name.casefold(): value for name, value in node.inputs.items()}
    for name in names:
        if name.casefold() not in lowered:
            continue
        value = unwrap_content(lowered[name.casefold()])
        if not isinstance(value, (dict, list)):
            return value
    return None


def _returns_to_choice_menu(summary: QuestSummary, graph: Graph) -> bool:
    """Whether the analyzed execution route explicitly navigates back to a menu."""
    return any(
        target in graph.nodes and graph.nodes[target].type_name == "Flow_MultiAnswer"
        for _, _, target in summary.flow_steps
    )


def _event_name(node: Node) -> str | None:
    event = node.raw.get("eventName")
    value = event.get("_value") if isinstance(event, dict) else None
    return str(value) if value else None


def _branch_accepts_value(port: str, value: Any) -> bool:
    if not isinstance(value, (bool, int, float)):
        return False
    match = re.match(r"^\s*(>=|<=|==|>|<)\s*(-?\d+(?:\.\d+)?)\s*$", port)
    if not match:
        return False
    expected = float(match.group(2))
    actual = float(value)
    return {
        ">=": actual >= expected,
        "<=": actual <= expected,
        "==": actual == expected,
        ">": actual > expected,
        "<": actual < expected,
    }[match.group(1)]


def _reachable_paths(graph: Graph, start: str, target_type: str,
                     max_depth: int = 200) -> list[list[str]]:
    results: list[list[str]] = []
    queue: deque[tuple[str, list[str]]] = deque([(start, [start])])
    while queue:
        current, path = queue.popleft()
        if len(path) > max_depth:
            continue
        node = graph.nodes[current]
        if current != start and node.type_name == target_type:
            results.append(path)
        if node.type_name == "Return":
            continue
        outgoing = graph.outgoing_flow[current]
        if node.type_name == "CustomFunctionCall":
            call_edges = [edge for edge in outgoing if edge.raw_type == "Synthetic.CustomFunctionCall"]
            if call_edges:
                outgoing = call_edges
        for edge in outgoing:
            if edge.target not in path:
                queue.append((edge.target, path + [edge.target]))
    return results


def _flow_reachable(graph: Graph, start: str, target: str, max_states: int = 10_000) -> bool:
    if start == target:
        return True
    visited = {start}
    queue = deque([start])
    while queue and len(visited) <= max_states:
        current = queue.popleft()
        for edge in graph.outgoing_flow[current]:
            if edge.target == target:
                return True
            if edge.target not in visited:
                visited.add(edge.target)
                queue.append(edge.target)
    return False


def _flow_depths(graph: Graph) -> dict[str, int]:
    """Return shortest flow distance from a graph entry, including call edges.

    Conversation menus frequently form cycles because a submenu returns to the
    NPC's main menu. Shortest entry distance gives those menus a stable
    hierarchy: the forward transition enters a deeper menu, while the return
    transition points back to a shallower one.
    """
    roots = sorted(
        node_id for node_id in graph.nodes
        if not graph.incoming_flow[node_id]
    )
    depths = {node_id: 0 for node_id in roots}
    queue = deque(roots)
    while queue:
        current = queue.popleft()
        next_depth = depths[current] + 1
        for edge in graph.outgoing_flow[current]:
            if edge.target in depths and depths[edge.target] <= next_depth:
                continue
            depths[edge.target] = next_depth
            queue.append(edge.target)
    return depths


def _backward_root_paths(graph: Graph, target: str, max_paths: int = 32,
                         max_depth: int = 200) -> tuple[list[tuple[list[str], list[Edge]]], list[str]]:
    results: list[tuple[list[str], list[Edge]]] = []
    issues: list[str] = []
    stack: list[tuple[str, list[str], list[Edge]]] = [(target, [target], [])]
    while stack and len(results) < max_paths:
        current, reverse_nodes, reverse_edges = stack.pop()
        if len(reverse_nodes) > max_depth:
            issues.append(f"depth limit {max_depth} reached")
            continue
        incoming = graph.incoming_flow[current]
        if not incoming:
            results.append((list(reversed(reverse_nodes)), list(reversed(reverse_edges))))
            continue
        progressed = False
        for edge in reversed(incoming):
            if edge.source in reverse_nodes:
                issues.append(f"loop through node {edge.source} skipped")
                continue
            progressed = True
            stack.append((edge.source, reverse_nodes + [edge.source], reverse_edges + [edge]))
        if not progressed:
            results.append((list(reversed(reverse_nodes)), list(reversed(reverse_edges))))
    if stack:
        issues.append(f"path limit {max_paths} reached")
    return results, sorted(set(issues))


def _entry_label(node: Node) -> str:
    event = _event_name(node)
    return f"{node.type_name}" + (f" ({event})" if event else "")


def _player_state_changes(graph: Graph, node_ids: set[str] | list[str]) -> list[dict[str, str]]:
    changes: list[dict[str, str]] = []
    for node_id in node_ids:
        node = graph.nodes[node_id]
        if node.type_name not in {"Flow_SetPlayerParam", "Flow_AddPlayerParam"}:
            continue
        parameter, value = _input(node, "Param name", "param"), _input(node, "Value", "value")
        change = {
            "operation": "set" if node.type_name == "Flow_SetPlayerParam" else "add",
            "parameter": str(parameter), "value": display_value(value), "node": node.id,
        }
        if parameter is not None and value is not None and change not in changes:
            changes.append(change)
    return changes


def _run_script_calls(graph: Graph, node_ids: set[str] | list[str]) -> list[dict[str, str]]:
    calls: list[dict[str, str]] = []
    for node_id in node_ids:
        node = graph.nodes[node_id]
        if node.type_name != "Flow_RunScript":
            continue
        script = _input(node, "Script name")
        # A leading colon addresses an event inside the current graph. It is not
        # a GS.RunFlowScript call and therefore must not create a cross-graph edge.
        if not isinstance(script, str) or not script or script.startswith(":"):
            continue
        call = {"node": node.id, "script": script}
        if call not in calls:
            calls.append(call)
    return calls


def _emitted_event(node: Node) -> tuple[str, str] | None:
    fields = {
        "Flow_FireEvent": ("event", "fires"),
        "Flow_AddInteractionEvent": ("Event", "enables interaction"),
        "Flow_GoTo": ("finished_event", "on arrival"),
    }
    field_and_kind = fields.get(node.type_name)
    if field_and_kind is None:
        return None
    event = _input(node, field_and_kind[0])
    if not isinstance(event, str) or not event:
        return None
    return event, field_and_kind[1]


def _script_graph_name(script: str, graph_lookup: dict[str, Graph]) -> str | None:
    normalized = script.replace("\\", "/").removesuffix(".json")
    candidates = (normalized, normalized.rsplit("/", 1)[-1])
    names = {name.casefold(): name for name in graph_lookup}
    for candidate in candidates:
        if candidate.casefold() in names:
            return names[candidate.casefold()]
    return None


def _event_wgo_graphs(node: Node, graph: Graph,
                      graph_lookup: dict[str, Graph]) -> set[str]:
    """Resolve the WGO feeding an event node to likely FlowGraph names.

    Flow_FindWGO usually stores the target's custom_tag directly. Some scripts
    build object ids (for example ``church_budka_`` + loop index), so prefixes
    are useful evidence too. Only WGO-identifying input names are considered.
    """
    candidate_values: set[str] = set()
    queue: deque[tuple[str, str]] = deque([(node.id, "WGO")])
    visited: set[tuple[str, str]] = set()
    identifying_inputs = {"custom_tag", "obj_id", "wgo_obj_id", "str0"}
    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        for edge in graph.incoming_data.get(current, []):
            source = graph.nodes[edge.source]
            for key in identifying_inputs:
                value = _input(source, key)
                if isinstance(value, str) and value:
                    candidate_values.add(value)
            for (target_id, target_port) in graph.incoming_data:
                if target_id == source.id:
                    queue.append((target_id, target_port))

    result: set[str] = set()
    names = {name.casefold(): name for name in graph_lookup}
    for value in candidate_values:
        normalized = value.replace("\\", "/").rsplit("/", 1)[-1].removesuffix(".json")
        exact = names.get(normalized.casefold())
        if exact:
            result.add(exact)
        if normalized.endswith("_"):
            result.update(
                name for folded, name in names.items()
                if folded.startswith(normalized.casefold())
            )
    return result


def _standalone_unlock_data(graph: Graph, node_id: str, phrase: str
                            ) -> tuple[dict[str, Any], set[str], set[tuple[str, str, str]]]:
    paths, issues = _backward_root_paths(graph, node_id)
    node_ids = {current for path, _ in paths for current in path}
    steps = {(edge.source, edge.source_port, edge.target) for _, edges in paths for edge in edges}
    entries = list(dict.fromkeys(_entry_label(graph.nodes[path[0]]) for path, _ in paths if path))
    conversations: list[str] = []
    task_states: list[dict[str, str]] = []
    function_calls: list[str] = []
    requirements: list[str] = []
    for current in node_ids:
        node = graph.nodes[current]
        if node.type_name == "Flow_Talk":
            text = _input(node, "Text")
            if isinstance(text, str) and text and text not in conversations:
                conversations.append(text)
        elif node.type_name == "Flow_SetTaskState":
            task, state = _input(node, "Task"), _input(node, "State")
            value = {"task": str(task), "state": str(state)}
            if task is not None and state is not None and value not in task_states:
                task_states.append(value)
        elif node.type_name == "CustomFunctionCall":
            for edge in graph.outgoing_flow[node.id]:
                if edge.raw_type != "Synthetic.CustomFunctionCall":
                    continue
                event = graph.nodes[edge.target]
                identifier = event.raw.get("identifier")
                label = str(identifier) if identifier else event.type_name
                call = f"{node.id} -> {label} (CustomFunctionEvent {event.id})"
                if call not in function_calls:
                    function_calls.append(call)
        elif node.type_name == "Flow_RunScript":
            script = _input(node, "Script name")
            if isinstance(script, str) and script:
                call = f"{node.id} -> {script} (Flow_RunScript)"
                if call not in function_calls:
                    function_calls.append(call)
    for source, port, _ in sorted(steps):
        node = graph.nodes[source]
        if node.type_name == "Flow_PlayerFlag":
            requirement = f"Flow_PlayerFlag {_input(node, 'param', 'Param name')} -> {port}"
        elif node.type_name in {"Flow_PlayerParamCompare", "Flow_PlayerParamCompareInt"}:
            requirement = (f"{node.type_name} {_input(node, 'param', 'Param name')} "
                           f"{port} {display_value(_input(node, 'value', 'Value'))}")
        else:
            continue
        if requirement not in requirements:
            requirements.append(requirement)
    is_blacklist_removal = (
        graph.nodes[node_id].type_name == "Flow_AddPhraseToBlacklist"
        and bool(_input(graph.nodes[node_id], "remove"))
    )
    data = {
        "id": f"unlock:{graph.name}.json:{node_id}", "file": f"{graph.name}.json", "graph": graph.name,
        "multiAnswer": None, "multiAnswerNode": None, "multiAnswerNodes": [], "rewards": [], "requiredQuests": [], "requiredQuestSources": [],
        "requiredHappiness": [], "requiredItems": [], "costs": [], "otherRequirements": requirements,
        "functionCalls": function_calls,
        "conversations": conversations, "taskStates": task_states,
        "phrasesToBlacklist": [],
        "phrasesRemovedFromBlacklist": [phrase] if is_blacklist_removal else [],
        "phrasesUnlocked": [] if is_blacklist_removal else [phrase],
        "stateEventLinks": [], "playerStateChanges": _player_state_changes(graph, node_ids),
        "playerStateLinks": [], "scriptLinks": [], "eventLinks": [], "externalSources": [],
        "entryEvents": entries, "choiceLinks": [], "choiceAlternatives": [], "uncertainties": issues,
    }
    return data, node_ids, steps


def _standalone_action_data(graph: Graph, node_id: str, reference: str
                            ) -> tuple[dict[str, Any], set[str], set[tuple[str, str, str]]]:
    data, node_ids, steps = _standalone_unlock_data(graph, node_id, "")
    data["id"] = reference
    data["phrasesUnlocked"] = []
    data["phrasesRemovedFromBlacklist"] = []
    return data, node_ids, steps


def _comparison_branch_accepts(node: Node, port: str, value: Any) -> bool:
    if node.type_name == "Flow_PlayerFlag":
        return _branch_accepts_value(port, value)
    if (node.type_name not in {"Flow_PlayerParamCompare", "Flow_PlayerParamCompareInt"}
            or not isinstance(value, (bool, int, float))):
        return False
    threshold = _input(node, "value", "Value")
    if not isinstance(threshold, (bool, int, float)):
        return False
    operator = port.strip()
    if operator not in {">=", "<=", "!=", "==", ">", "<"}:
        return False
    actual, expected = float(value), float(threshold)
    return {
        ">=": actual >= expected, "<=": actual <= expected, "!=": actual != expected,
        "==": actual == expected,
        ">": actual > expected, "<": actual < expected,
    }[operator]


def _change_contributes(node: Node, port: str, value: Any) -> bool:
    if not isinstance(value, (int, float)) or value == 0:
        return False
    operator = port.strip().split(maxsplit=1)[0]
    return ((value > 0 and operator in {">", ">="})
            or (value < 0 and operator in {"<", "<="}))


def _player_state_bridges(
        analyses: list[GraphAnalysis], owner_nodes: dict[str, tuple[str, set[str]]],
        owner_steps: dict[str, set[tuple[str, str, str]]]) -> list[dict[str, str]]:
    graphs = {analysis.graph.name: analysis.graph for analysis in analyses}
    setters: dict[str, list[tuple[str, Node, str, Any]]] = {}
    checks: dict[str, list[tuple[str, Node, str]]] = {}
    for owner, (graph_name, node_ids) in owner_nodes.items():
        graph = graphs[graph_name]
        for node_id in node_ids:
            node = graph.nodes[node_id]
            if node.type_name not in {"Flow_SetPlayerParam", "Flow_AddPlayerParam"}:
                continue
            parameter = _input(node, "Param name", "param")
            value = _input(node, "Value", "value")
            if isinstance(parameter, str) and isinstance(value, (bool, int, float)):
                setters.setdefault(parameter, []).append((owner, node, graph_name, value))
        for source, port, _ in owner_steps.get(owner, set()):
            node = graph.nodes[source]
            if node.type_name not in {
                "Flow_PlayerFlag", "Flow_PlayerParamCompare", "Flow_PlayerParamCompareInt",
            }:
                continue
            parameter = _input(node, "param", "Param name")
            if isinstance(parameter, str):
                checks.setdefault(parameter, []).append((owner, node, port))

    bridges: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for parameter, parameter_checks in checks.items():
        for source, setter, source_graph, value in setters.get(parameter, []):
            for target, checker, port in parameter_checks:
                if source == target:
                    continue
                operation = "set" if setter.type_name == "Flow_SetPlayerParam" else "add"
                if operation == "set" and not _comparison_branch_accepts(checker, port, value):
                    continue
                if operation == "add" and not _change_contributes(checker, port, value):
                    continue
                key = source, target, parameter, f"{checker.id}.{port}"
                if key in seen:
                    continue
                seen.add(key)
                target_graph = owner_nodes[target][0]
                bridges.append({
                    "from": source, "to": target, "parameter": parameter,
                    "operation": operation, "value": display_value(value),
                    "setter": f"{source_graph}.json:{setter.id}",
                    "check": f"{target_graph}.json:{checker.id}.{port}",
                    "certainty": "satisfies" if operation == "set" else "contributes",
                })
    return bridges


def _state_event_bridges(
        analyses: list[GraphAnalysis], summaries: list[QuestSummary],
        unlock_owners: dict[tuple[str, str], str]) -> list[dict[str, str]]:
    """Infer delayed quest links implemented through WGO flag -> registered event -> CustomEvent."""
    summaries_by_graph: dict[str, list[QuestSummary]] = {}
    for summary in summaries:
        summaries_by_graph.setdefault(summary.graph, []).append(summary)

    bridges: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for analysis in analyses:
        graph = analysis.graph
        graph_summaries = summaries_by_graph.get(graph.name, [])
        custom_events: dict[str, list[str]] = {}
        for node in graph.nodes.values():
            if node.type_name == "CustomEvent" and _event_name(node):
                custom_events.setdefault(_event_name(node) or "", []).append(node.id)

        for source in graph_summaries:
            setters = [graph.nodes[node_id] for node_id in source.node_ids
                       if graph.nodes[node_id].type_name == "Flow_SetWGOParam"]
            for setter in setters:
                parameter = _input(setter, "Param name", "param")
                value = _input(setter, "Value", "value")
                if not isinstance(parameter, str) or not isinstance(value, (bool, int, float)):
                    continue
                for checker in graph.nodes.values():
                    if checker.type_name != "Flow_ParamFlag" or _input(checker, "param", "Param name") != parameter:
                        continue
                    matching_edges = [edge for edge in graph.outgoing_flow[checker.id]
                                      if _branch_accepts_value(edge.source_port, value)]
                    for branch in matching_edges:
                        interaction_paths = _reachable_paths(graph, checker.id, "Flow_AddInteractionEvent")
                        interaction_paths = [path for path in interaction_paths
                                             if len(path) > 1 and path[1] == branch.target]
                        for interaction_path in interaction_paths:
                            interaction = graph.nodes[interaction_path[-1]]
                            event = _input(interaction, "Event")
                            if not isinstance(event, str) or not event:
                                continue
                            for entry_id in custom_events.get(event, []):
                                unlock_paths = _reachable_paths(graph, entry_id, "Flow_UnlockPhrase")
                                for unlock_path in unlock_paths:
                                    unlock_id = unlock_path[-1]
                                    target = unlock_owners.get((graph.name, unlock_id))
                                    if not target or target == source.reference:
                                        continue
                                    key = source.reference, target, parameter, event
                                    if key in seen:
                                        continue
                                    seen.add(key)
                                    bridges.append({
                                        "from": source.reference,
                                        "to": target,
                                        "parameter": parameter,
                                        "value": display_value(value),
                                        "check": f"{checker.id}.{branch.source_port}",
                                        "interactionEvent": event,
                                        "setter": setter.id,
                                        "eventEntry": entry_id,
                                        "unlock": unlock_id,
                                        "flagPath": " -> ".join(interaction_path),
                                        "eventPath": " -> ".join(unlock_path),
                                    })
    return bridges


def _label(summary: QuestSummary) -> str:
    if summary.multi_answer:
        return summary.multi_answer[1:] if summary.multi_answer.startswith("@") else summary.multi_answer
    rewards = _reward_dicts(summary)
    if rewards:
        reward = rewards[0]
        if reward["type"] == "relation":
            return f"{summary.graph}: +{reward['amount']} relation"
        return f"{summary.graph}: {reward['item']}"
    return summary.reference


def _tooltip(data: dict[str, Any]) -> str:
    parts = []
    if data.get("displayName"):
        parts.append(f"<b>{html.escape(data['displayName'])}</b>")
    if data.get("technicalName"):
        parts.append(f"Original node name: {html.escape(data['technicalName'])}")
    parts.append(f"File: {html.escape(data['file'])}")
    if data.get("contentPack"):
        parts.append(f"Content: {html.escape(data['contentPack'])}")
    if data["multiAnswer"]:
        parts.append(f"Phrase: {html.escape(data['multiAnswer'])}")
    if len(data.get("multiAnswerNodes", [])) > 1:
        parts.append("Available in MultiAnswer menus: " + ", ".join(
            html.escape(value) for value in data["multiAnswerNodes"]
        ))
    for reward in data["rewards"]:
        if reward["type"] == "relation":
            parts.append(f"Reward: +{html.escape(reward['amount'])} relation ({html.escape(reward['npc'])})")
        else:
            parts.append(f"Reward: {html.escape(reward['item'])} x{html.escape(reward['amount'])}")
    if data["requiredQuests"]:
        parts.append("Requires: " + ", ".join(html.escape(value) for value in data["requiredQuests"]))
    if data["phrasesUnlocked"]:
        parts.append("Unlocks: " + ", ".join(html.escape(value) for value in data["phrasesUnlocked"]))
    if data.get("functionCalls"):
        parts.append("Calls: " + ", ".join(html.escape(value) for value in data["functionCalls"]))
    if data.get("unresolvedEntry"):
        parts.append("<b>Entry source unresolved — reward retained</b>")
    for link in data.get("stateEventLinks", []):
        verb = "Enables" if link["direction"] == "enables" else "Requires"
        parts.append(
            f"{verb}: {html.escape(link['parameter'])}={html.escape(link['value'])} "
            f"→ {html.escape(link['interactionEvent'])}"
        )
    for link in data.get("playerStateLinks", []):
        verb = "Sets" if link["direction"] == "provides" else "Needs"
        parts.append(
            f"{verb}: {html.escape(link['parameter'])} "
            f"({html.escape(link['setter'])} → {html.escape(link['check'])})"
        )
    for link in data.get("choiceLinks", []):
        verb = "Next choice" if link["direction"] == "continues" else "From choice"
        parts.append(f"{verb}: {html.escape(link['phrase'])}")
    for source in data.get("externalSources", []):
        parts.append(
            f"GameData: {html.escape(str(source.get('trigger', source.get('record', ''))))} "
            f"→ {html.escape(str(source.get('script', '')))}"
        )
    if len(data.get("choiceAlternatives", [])) > 1:
        parts.append("Alternatives: " + ", ".join(
            html.escape(value["phrase"]) for value in data["choiceAlternatives"]
        ))
    return "<br>".join(parts)


def _content_pack(data: dict[str, Any]) -> str:
    # Classify a finding by its own semantic identifiers. Cross-graph source and
    # bridge metadata must not make a Base Game node inherit a neighbor's DLC.
    identity = {
        key: data.get(key) for key in (
            "file", "multiAnswer", "rewards", "requiredQuests", "requiredItems", "costs",
            "otherRequirements", "functionCalls", "conversations", "taskStates",
            "phrasesToBlacklist", "phrasesRemovedFromBlacklist", "phrasesUnlocked",
            "playerStateChanges", "entryEvents", "choiceAlternatives",
        )
    }
    corpus = json.dumps(identity, ensure_ascii=False, sort_keys=True).casefold()
    if "souls" in corpus:
        return "Better Call Soul"
    if "refugee" in corpus:
        return "Game of Crone"
    if re.search(r"(?:^|[^a-z0-9])tr_", corpus):
        return "Stranger Sins"
    if re.search(r"(?:^|[^a-z0-9])\d+cs(?:[^a-z0-9]|$)", corpus):
        return "Stranger Sins"
    return "Base Game"


def _assign_content_packs(nodes: list[dict[str, Any]], details: dict[str, dict[str, Any]],
                          edges: list[dict[str, Any]]) -> dict[str, int]:
    menu_ids = {node["id"] for node in nodes if node["group"] == "choice_menu"}
    for node in nodes:
        if node["id"] in menu_ids:
            continue
        details[node["id"]]["contentPack"] = _content_pack(details[node["id"]])

    neighbors: dict[str, set[str]] = {node_id: set() for node_id in menu_ids}
    for edge in edges:
        if edge["from"] in menu_ids and edge["to"] in details:
            neighbors[edge["from"]].add(edge["to"])
        if edge["to"] in menu_ids and edge["from"] in details:
            neighbors[edge["to"]].add(edge["from"])
    for menu_id in menu_ids:
        packs = {
            details[other].get("contentPack", "Base Game")
            for other in neighbors[menu_id] if other not in menu_ids
        }
        details[menu_id]["contentPack"] = next(iter(packs)) if len(packs) == 1 else "Base Game"

    counts = {name: 0 for name in CONTENT_PACKS}
    for node in nodes:
        data = details[node["id"]]
        pack = data["contentPack"]
        counts[pack] += 1
        node["contentPack"] = pack
        node["title"] = _tooltip(data)
        node["search"] = json.dumps(data, ensure_ascii=False).casefold()
    return counts


def _choice_outcome_signature(summary: QuestSummary) -> str:
    own_phrase = (summary.multi_answer or "").removeprefix("@")
    payload = {
        "rewards": _reward_dicts(summary),
        "taskStates": [(value.task, value.state) for value in summary.task_states],
        "phrasesUnlocked": summary.phrases_unlocked,
        "phrasesToBlacklist": [
            value for value in summary.phrases_to_blacklist if value != own_phrase
        ],
        "phrasesRemovedFromBlacklist": [
            value for value in summary.phrases_removed_from_blacklist if value != own_phrase
        ],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _duplicate_finding_signature(summary: QuestSummary) -> str:
    """Identify one executable finding offered by multiple MultiAnswer menus."""
    data = _summary_data(summary)
    for key in (
        "id", "multiAnswerNode", "multiAnswerNodes", "requiredQuestSources",
            "stateEventLinks", "playerStateLinks", "scriptLinks", "eventLinks", "externalSources",
            "choiceLinks", "choiceAlternatives",
        "uncertainties",
    ):
        data.pop(key, None)
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _choice_alternative(summary: QuestSummary) -> dict[str, Any]:
    return {
        "id": summary.reference,
        "phrase": summary.multi_answer or f"option {summary.multi_answer_index}",
        "option": summary.multi_answer_index,
        "requiredQuests": summary.required_quests,
        "requiredHappiness": [{
            "amount": display_value(value.amount), "npc": value.npc or "unresolved",
            "npcSource": value.npc_source,
        } for value in summary.required_happiness],
        "requiredItems": summary.required_items,
        "costs": summary.costs,
        "otherRequirements": summary.other_requirements,
        "conversations": summary.conversations,
        "functionCalls": summary.function_calls,
    }


def _choice_menu_data(graph: str, menu_id: str) -> dict[str, Any]:
    return {
        "id": f"choice-menu:{graph}:{menu_id}",
        "file": f"{graph}.json",
        "graph": graph,
        "multiAnswer": f"Choice menu {menu_id}",
        "multiAnswerNode": menu_id,
        "multiAnswerNodes": [menu_id],
        "rewards": [],
        "requiredQuests": [],
        "requiredQuestSources": [],
        "requiredHappiness": [],
        "requiredItems": [],
        "costs": [],
        "otherRequirements": [
            "Conversation choices are revisitable unless another condition disables them"
        ],
        "functionCalls": [],
        "conversations": [],
        "taskStates": [],
        "phrasesToBlacklist": [],
        "phrasesRemovedFromBlacklist": [],
        "phrasesUnlocked": [],
        "stateEventLinks": [],
        "playerStateChanges": [],
        "playerStateLinks": [],
        "scriptLinks": [],
        "eventLinks": [],
        "externalSources": [],
        "entryEvents": [],
        "choiceLinks": [],
        "choiceAlternatives": [],
        "unresolvedEntry": False,
        "uncertainties": [],
    }


def _add_item_requirement_edges(nodes: list[dict[str, Any]],
                                details: dict[str, dict[str, Any]],
                                edges: list[dict[str, Any]]) -> None:
    """Connect explicit Flow rewards to item-consuming GameData entry points.

    Restricting this bridge to GameData records keeps ordinary commodities from
    turning dialogue choices into enormous producer/consumer meshes. It still
    captures quest crafts such as the portal barrel and emitter, whose input
    items are awarded by several otherwise independent quest lines.
    """
    reward_sources: dict[str, list[str]] = {}
    for node in nodes:
        for reward in details[node["id"]].get("rewards", []):
            if reward.get("type") != "item_drop":
                continue
            item = reward.get("item")
            if isinstance(item, str) and item not in {"", "dynamic/unresolved"}:
                reward_sources.setdefault(item, []).append(node["id"])

    existing = {
        (edge["from"], edge["to"], edge.get("kind")) for edge in edges
    }
    for target in nodes:
        data = details[target["id"]]
        if not data.get("externalSources"):
            continue
        for requirement in data.get("requiredItems", []):
            item = str(requirement).rsplit(" x", 1)[0]
            for source in reward_sources.get(item, []):
                key = source, target["id"], "item_requirement"
                if source == target["id"] or key in existing:
                    continue
                existing.add(key)
                edges.append({
                    "id": f"edge:{len(edges)}", "from": source, "to": target["id"],
                    "label": f"provides {item}",
                    "title": html.escape(f"Reward item {item} satisfies {requirement}"),
                    "arrows": "to", "kind": "item_requirement", "dashes": True,
                })


def _add_start_node(nodes: list[dict[str, Any]], details: dict[str, dict[str, Any]],
                    edges: list[dict[str, Any]]) -> None:
    """Join conservatively proven, initially visible Base Game answers."""
    incoming = {edge["to"] for edge in edges}
    targets: dict[str, str] = {}
    initial_evidence = "Beim neuen Spiel sichtbar (MultiAnswerGUI-Regel: kein @-Präfix)"
    for node in nodes:
        data = details[node["id"]]
        phrase = data.get("multiAnswer")
        game_start_source = any(
            source.get("trigger") == "game_start"
            for source in data.get("externalSources", [])
        )
        if (node.get("contentPack") == "Base Game" and node["id"] not in incoming
                and game_start_source):
            targets[node["id"]] = "quests_data.json start_key: game_start"
        elif (
            node.get("contentPack") == "Base Game"
            and node["id"] not in incoming
            and isinstance(phrase, str) and phrase and not phrase.startswith("@")
            and initial_evidence in data.get("requiredQuestSources", [])
            and not any(data.get(key) for key in (
                "requiredHappiness", "requiredItems", "costs", "otherRequirements",
            ))
        ):
            targets[node["id"]] = initial_evidence
    if not targets:
        return

    node_id = "quest-start"
    data = _choice_menu_data("Game start", "start")
    data.update({
        "id": node_id, "file": "GameSave / MultiAnswerGUI", "graph": "Game start",
        "multiAnswer": "Start", "multiAnswerNode": None, "multiAnswerNodes": [],
        "otherRequirements": [], "contentPack": "Base Game",
    })
    details[node_id] = data
    nodes.append({
        "id": node_id, "label": "START", "title": _tooltip(data), "group": "start",
        "graph": "Game start", "value": 3, "contentPack": "Base Game",
        "search": json.dumps(data, ensure_ascii=False).casefold(),
    })
    for target, evidence in sorted(targets.items()):
        edges.append({
            "id": f"edge:{len(edges)}", "from": node_id, "to": target,
            "label": "available from start",
            "title": html.escape(evidence), "arrows": "to", "kind": "initial",
        })


def _prune_navigation_only_leaves(nodes: list[dict[str, Any]],
                                  details: dict[str, dict[str, Any]],
                                  edges: list[dict[str, Any]]) -> set[str]:
    """Remove proven dialogue-return leaves with no progression effect.

    A blacklist-only answer often exists solely to hide a consumed dialogue
    option before returning to the NPC's parent menu. It is useful while
    reconstructing control flow, but it is not a quest-graph outcome. Unknown
    paths and any state, reward, unlock, or cross-graph effect stay visible.
    """
    outgoing = {edge["from"] for edge in edges}
    removed = {
        node["id"] for node in nodes
        if node["group"] == "phrase"
        and node["id"] not in outgoing
        and details[node["id"]].get("returnsToChoiceMenu")
        and details[node["id"]].get("phrasesToBlacklist")
        and not details[node["id"]].get("uncertainties")
        and not any(details[node["id"]].get(key) for key in (
            "rewards", "taskStates", "phrasesUnlocked", "phrasesRemovedFromBlacklist",
            "playerStateChanges", "stateEventLinks", "playerStateLinks", "scriptLinks",
            "eventLinks",
        ))
    }
    if not removed:
        return removed
    nodes[:] = [node for node in nodes if node["id"] not in removed]
    edges[:] = [
        edge for edge in edges
        if edge["from"] not in removed and edge["to"] not in removed
    ]
    for node_id in removed:
        details.pop(node_id, None)
    return removed


def _assign_directed_layout(nodes: list[dict[str, Any]],
                            edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Assign stable left-to-right levels using the graph's SCC condensation."""
    ids = {node["id"] for node in nodes}
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in ids}
    for edge in edges:
        if edge["from"] in ids and edge["to"] in ids and edge["from"] != edge["to"]:
            adjacency[edge["from"]].add(edge["to"])

    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []

    def strong_connect(node_id: str) -> None:
        nonlocal index
        indices[node_id] = lowlinks[node_id] = index
        index += 1
        stack.append(node_id)
        on_stack.add(node_id)
        for target in sorted(adjacency[node_id]):
            if target not in indices:
                strong_connect(target)
                lowlinks[node_id] = min(lowlinks[node_id], lowlinks[target])
            elif target in on_stack:
                lowlinks[node_id] = min(lowlinks[node_id], indices[target])
        if lowlinks[node_id] != indices[node_id]:
            return
        component: list[str] = []
        while True:
            member = stack.pop()
            on_stack.remove(member)
            component.append(member)
            if member == node_id:
                break
        components.append(component)

    for node_id in sorted(ids):
        if node_id not in indices:
            strong_connect(node_id)

    component_of = {
        node_id: component_id
        for component_id, members in enumerate(components) for node_id in members
    }
    successors: dict[int, set[int]] = {component_id: set() for component_id in range(len(components))}
    predecessors: dict[int, set[int]] = {component_id: set() for component_id in range(len(components))}
    for source, targets in adjacency.items():
        source_component = component_of[source]
        for target in targets:
            target_component = component_of[target]
            if source_component == target_component:
                continue
            successors[source_component].add(target_component)
            predecessors[target_component].add(source_component)

    indegree = {component_id: len(values) for component_id, values in predecessors.items()}
    queue = deque(sorted(component_id for component_id, value in indegree.items() if value == 0))
    depth = {component_id: 0 for component_id in indegree}
    while queue:
        component_id = queue.popleft()
        for target in sorted(successors[component_id]):
            depth[target] = max(depth[target], depth[component_id] + 1)
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)

    buckets: dict[str, dict[int, list[dict[str, Any]]]] = {
        pack: {} for pack in CONTENT_PACKS
    }
    for node in nodes:
        node_depth = depth[component_of[node["id"]]]
        node["depth"] = node_depth
        buckets[node["contentPack"]].setdefault(node_depth, []).append(node)

    lane_heights = {
        pack: max(650, max((len(values) for values in by_depth.values()), default=1) * 105 + 220)
        for pack, by_depth in buckets.items()
    }
    cursor = 0.0
    lanes: list[dict[str, Any]] = []
    for pack in CONTENT_PACKS:
        height = lane_heights[pack]
        center = cursor + height / 2
        lanes.append({"name": pack, "y": center, "height": height})
        for node_depth, values in buckets[pack].items():
            values.sort(key=lambda value: (value["label"].casefold(), value["id"]))
            for position, node in enumerate(values):
                node["x"] = node_depth * 310
                node["y"] = center + (position - (len(values) - 1) / 2) * 105
        cursor += height + 180
    return lanes


def _apply_node_aliases(nodes: list[dict[str, Any]], details: dict[str, dict[str, Any]],
                        edges: list[dict[str, Any]], aliases: dict[str, str]) -> None:
    if not aliases:
        return

    def canonical(node_id: str) -> str:
        while node_id in aliases:
            node_id = aliases[node_id]
        return node_id

    nodes[:] = [node for node in nodes if node["id"] not in aliases]
    for alias in aliases:
        details.pop(alias, None)
    deduplicated: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for edge in edges:
        edge["from"] = canonical(edge["from"])
        edge["to"] = canonical(edge["to"])
        if edge["from"] == edge["to"]:
            continue
        key = edge["from"], edge["to"], edge.get("label", ""), edge.get("kind", "")
        if key in seen:
            continue
        seen.add(key)
        edge["id"] = f"edge:{len(deduplicated)}"
        deduplicated.append(edge)
    edges[:] = deduplicated
    for data in details.values():
        for collection in (
                "choiceLinks", "stateEventLinks", "playerStateLinks", "scriptLinks", "eventLinks"):
            for link in data.get(collection, []):
                if "other" in link:
                    link["other"] = canonical(link["other"])


def build_quest_graph_data(analyses: list[GraphAnalysis],
                           phrase_unlocks: dict[str, list[str]] | None = None,
                           game_data_scripts: dict[str, list[dict[str, Any]]] | None = None,
                           node_names: dict[str, str] | None = None,
                           ) -> dict[str, Any]:
    phrase_unlocks = phrase_unlocks or build_phrase_unlock_index(analyses)
    game_data_scripts = game_data_scripts or {}
    all_summaries: list[QuestSummary] = []
    for analysis in analyses:
        all_summaries.extend(build_quest_summaries(
            analysis, phrase_unlocks, include_without_rewards=True))

    graph_lookup = {analysis.graph.name: analysis.graph for analysis in analyses}
    included = [summary for summary in all_summaries if (
        not summary.graph.casefold().startswith("test_")
        and (
            summary.reward_count or summary.phrases_unlocked or summary.phrases_to_blacklist or
            summary.phrases_removed_from_blacklist or
            _run_script_calls(graph_lookup[summary.graph], summary.node_ids) or
            any(_emitted_event(graph_lookup[summary.graph].nodes[node_id])
                for node_id in summary.node_ids)
        )
    )]
    nodes: list[dict[str, Any]] = []
    details: dict[str, dict[str, Any]] = {}
    unlockers: dict[str, list[str]] = {}
    unlock_owners: dict[tuple[str, str], str] = {}
    owner_nodes: dict[str, tuple[str, set[str]]] = {}
    owner_steps: dict[str, set[tuple[str, str, str]]] = {}
    for summary in included:
        data = _summary_data(summary)
        data["returnsToChoiceMenu"] = _returns_to_choice_menu(
            summary, graph_lookup[summary.graph],
        )
        data["playerStateChanges"] = _player_state_changes(
            graph_lookup[summary.graph], summary.node_ids,
        )
        details[summary.reference] = data
        group = "reward" if summary.reward_count else "phrase"
        nodes.append({
            "id": summary.reference, "label": _label(summary), "title": _tooltip(data),
            "group": group, "graph": summary.graph,
            "value": max(1, summary.reward_count + len(summary.phrases_unlocked)),
            "search": json.dumps(data, ensure_ascii=False).casefold(),
        })
        for phrase in summary.phrases_unlocked + summary.phrases_removed_from_blacklist:
            unlockers.setdefault(phrase, []).append(summary.reference)
        owner_nodes[summary.reference] = (summary.graph, set(summary.node_ids))
        owner_steps[summary.reference] = set(summary.flow_steps)

    for summary in included:
        graph = graph_lookup[summary.graph]
        for node_id in summary.node_ids:
            node = graph.nodes[node_id]
            if (node.type_name == "Flow_UnlockPhrase" or (
                    node.type_name == "Flow_AddPhraseToBlacklist"
                    and bool(_input(node, "remove")))):
                unlock_owners[(summary.graph, node_id)] = summary.reference

    # Keep an unlock visible even when its surrounding flow has no reward/blacklist summary.
    for phrase, sources in phrase_unlocks.items():
        for source in sources:
            graph = source.rsplit(".json:", 1)[0]
            if graph.casefold().startswith("test_"):
                continue
            source_node_id = source.rsplit(":", 1)[1]
            if (graph, source_node_id) in unlock_owners:
                continue
            node_id = f"unlock:{source}"
            data, path_nodes, path_steps = _standalone_unlock_data(
                graph_lookup[graph], source_node_id, phrase)
            details[node_id] = data
            entry = data["entryEvents"][0] if data["entryEvents"] else "external entry"
            nodes.append({
                "id": node_id, "label": f"{graph}: {entry}", "title": _tooltip(data),
                "group": "unlock", "graph": graph, "value": 1,
                "search": json.dumps(data, ensure_ascii=False).casefold(),
            })
            unlockers.setdefault(phrase, []).append(node_id)
            unlock_owners[(graph, source_node_id)] = node_id
            owner_nodes[node_id] = (graph, path_nodes)
            owner_steps[node_id] = path_steps

    def add_bridge_owner(reference: str, graph: Graph, action_node_id: str,
                         label: str) -> None:
        data, path_nodes, path_steps = _standalone_action_data(
            graph, action_node_id, reference)
        details[reference] = data
        entry = data["entryEvents"][0] if data["entryEvents"] else "external entry"
        nodes.append({
            "id": reference, "label": f"{graph.name}: {label} ({entry})",
            "title": _tooltip(data), "group": "bridge", "graph": graph.name, "value": 1,
            "search": json.dumps(data, ensure_ascii=False).casefold(),
        })
        owner_nodes[reference] = (graph.name, path_nodes)
        owner_steps[reference] = path_steps

    # Pure dispatcher graphs contain no reward or phrase effect and therefore
    # have no QuestSummary. Preserve their root-to-call path as a compact bridge
    # so Flow_RunScript chains do not break at such intermediary scripts.
    owned_graph_nodes: dict[str, set[str]] = {}
    for owner_graph_name, owned_nodes in owner_nodes.values():
        owned_graph_nodes.setdefault(owner_graph_name, set()).update(owned_nodes)
    for graph in graph_lookup.values():
        if graph.name.casefold().startswith("test_"):
            continue
        for node in graph.nodes.values():
            if node.type_name != "Flow_RunScript" or node.id in owned_graph_nodes.get(graph.name, set()):
                continue
            calls = _run_script_calls(graph, {node.id})
            if not calls or _script_graph_name(calls[0]["script"], graph_lookup) is None:
                continue
            reference = f"script-call:{graph.name}.json:{node.id}"
            add_bridge_owner(reference, graph, node.id, f"runs {calls[0]['script']}")

    edges: list[dict[str, Any]] = []
    edge_keys: set[tuple[str, str, str]] = set()

    for script, sources in sorted(game_data_scripts.items()):
        target_graph_name = _script_graph_name(script, graph_lookup)
        if target_graph_name is None:
            continue
        target_graph = graph_lookup[target_graph_name]
        start_nodes = {
            node.id for node in target_graph.nodes.values() if node.type_name == "StartEvent"
        }
        for source_index, source in enumerate(sources):
            is_attached_script = source["field"].casefold().endswith("attached_script")
            targets: list[str] = []
            for target, (owner_graph_name, target_node_ids) in owner_nodes.items():
                if owner_graph_name != target_graph_name:
                    continue
                menu_id = details[target].get("multiAnswerNode")
                menu_reachable = bool(menu_id and any(
                    _flow_reachable(target_graph, start, str(menu_id)) for start in start_nodes
                ))
                if is_attached_script and menu_id and not menu_reachable:
                    menu_reachable = any(
                        _flow_reachable(target_graph, entry.id, str(menu_id))
                        for entry in target_graph.nodes.values()
                        if entry.type_name == "CustomEvent"
                    )
                custom_event_entry = is_attached_script and any(
                    target_graph.nodes[node_id].type_name == "CustomEvent"
                    for node_id in target_node_ids
                )
                if start_nodes.intersection(target_node_ids) or menu_reachable or custom_event_entry:
                    targets.append(target)
            if not targets:
                continue
            reference = f"game-data:{script}:{source['file']}:{source['record']}:{source['field']}:{source_index}"
            trigger = source.get("trigger") or source["record"]
            data = _choice_menu_data(target_graph_name, "external")
            data.update({
                "id": reference, "file": source["file"], "multiAnswer": None,
                "multiAnswerNode": None, "multiAnswerNodes": [],
                "otherRequirements": [str(trigger)],
                "requiredItems": source.get("requiredItems", []),
                "externalSources": [{**source, "script": script}],
            })
            details[reference] = data
            nodes.append({
                "id": reference, "label": f"{trigger} → {script}", "title": _tooltip(data),
                "group": "bridge", "graph": target_graph_name, "value": 1,
                "search": json.dumps(data, ensure_ascii=False).casefold(),
            })
            for target in targets:
                label = f"starts {script}"
                key = reference, target, label
                if key in edge_keys:
                    continue
                edge_keys.add(key)
                edges.append({
                    "id": f"edge:{len(edges)}", "from": reference, "to": target,
                    "label": label,
                    "title": html.escape(
                        f"{source['file']}:{source['record']}.{source['field']} → "
                        f"{target_graph_name}.StartEvent"),
                    "arrows": "to", "kind": "game_data", "dashes": True,
                })
                details[target]["externalSources"].append({**source, "script": script})
    for summary in included:
        target_phrases = list(dict.fromkeys(summary.required_quests + summary.phrases_to_blacklist))
        for phrase in target_phrases:
            for source_id in unlockers.get(phrase, []):
                if source_id == summary.reference:
                    continue
                key = source_id, summary.reference, phrase
                if key in edge_keys:
                    continue
                edge_keys.add(key)
                edges.append({
                    "id": f"edge:{len(edges)}", "from": source_id, "to": summary.reference,
                    "label": phrase, "title": html.escape(phrase), "arrows": "to", "kind": "phrase",
                })

    summaries_by_menu: dict[tuple[str, str], list[QuestSummary]] = {}
    summaries_by_required_phrase: dict[str, list[QuestSummary]] = {}
    for summary in included:
        if summary.multi_answer_node is not None:
            summaries_by_menu.setdefault((summary.graph, summary.multi_answer_node), []).append(summary)
        for phrase in summary.required_quests:
            summaries_by_required_phrase.setdefault(phrase, []).append(summary)

    aliases: dict[str, str] = {}
    flow_depths = {name: _flow_depths(graph) for name, graph in graph_lookup.items()}
    menu_predecessors: dict[tuple[str, str], set[str]] = {}
    for parent in included:
        graph = graph_lookup[parent.graph]
        nested_menus = sorted({
            node_id for node_id in parent.node_ids
            if graph.nodes[node_id].type_name == "Flow_MultiAnswer"
            and node_id != parent.multi_answer_node
        })
        for menu_id in nested_menus:
            # Returning from a submenu to an already upstream menu is navigation,
            # not a new quest branch. Linking it to every main-menu option creates
            # the large all-to-all clusters seen in NPC conversation graphs. Only
            # suppress the shallower direction of a cycle; the original forward
            # transition into the submenu remains visible.
            if parent.multi_answer_node and _flow_reachable(
                    graph, menu_id, parent.multi_answer_node):
                depths = flow_depths[parent.graph]
                parent_depth = depths.get(parent.multi_answer_node)
                nested_depth = depths.get(menu_id)
                if (parent_depth is not None and nested_depth is not None
                        and nested_depth <= parent_depth):
                    continue
            if summaries_by_menu.get((parent.graph, menu_id)):
                menu_predecessors.setdefault((parent.graph, menu_id), set()).add(
                    parent.reference)

    def resolve_choice_outcome(choice: QuestSummary) -> tuple[QuestSummary, list[QuestSummary]]:
        current = choice
        relays: list[QuestSummary] = []
        visited = {choice.reference}
        while (
            not current.reward_count
            and not current.task_states
            and not current.phrases_removed_from_blacklist
            and len(current.phrases_unlocked) == 1
        ):
            own_phrase = (current.multi_answer or "").removeprefix("@")
            if any(value != own_phrase for value in current.phrases_to_blacklist):
                break
            candidates = [
                value for value in summaries_by_required_phrase.get(current.phrases_unlocked[0], [])
                if value.reference not in visited
            ]
            signatures = {_duplicate_finding_signature(value) for value in candidates}
            if not candidates or len(signatures) != 1:
                break
            relays.append(current)
            current = sorted(candidates, key=lambda value: value.reference)[0]
            visited.add(current.reference)
        return current, relays

    def choice_route_alternative(entry: QuestSummary, terminal: QuestSummary,
                                 relays: list[QuestSummary]) -> dict[str, Any]:
        alternative = _choice_alternative(terminal)
        alternative["id"] = entry.reference
        if not relays:
            return alternative
        alternative["viaPhrases"] = [
            value.multi_answer for value in relays if value.multi_answer
        ]
        route = [*relays, terminal]
        alternative["requiredQuests"] = list(dict.fromkeys(
            phrase for value in route for phrase in value.required_quests
        ))
        alternative["requiredItems"] = list(dict.fromkeys(
            item for value in route for item in value.required_items
        ))
        alternative["costs"] = list(dict.fromkeys(
            cost for value in route for cost in value.costs
        ))
        alternative["otherRequirements"] = list(dict.fromkeys(
            requirement for value in route for requirement in value.other_requirements
        ))
        alternative["conversations"] = list(dict.fromkeys(
            conversation
            for value in [terminal, *reversed(relays)]
            for conversation in value.conversations
        ))
        alternative["functionCalls"] = list(dict.fromkeys(
            call for value in route for call in value.function_calls
        ))
        return alternative

    # Equivalent answers are merged only inside an actually reached follow-up
    # menu. A dialogue-only phrase relay is projected onto its eventual outcome,
    # so it does not become a misleading quest/reward node of its own.
    canonical_choices: dict[tuple[str, str], list[QuestSummary]] = {}
    for menu_key in menu_predecessors:
        routes = [
            (choice, *resolve_choice_outcome(choice))
            for choice in summaries_by_menu[menu_key]
        ]
        projected_counts: dict[str, int] = {}
        for _, terminal, _ in routes:
            signature = _choice_outcome_signature(terminal)
            projected_counts[signature] = projected_counts.get(signature, 0) + 1
        outcome_groups: dict[str, list[tuple[QuestSummary, QuestSummary, list[QuestSummary]]]] = {}
        for choice, terminal, relays in routes:
            # A relay is hidden only when it lets this menu converge on an
            # outcome also reached by another answer. Unique chains remain
            # explicit quest findings.
            if relays and projected_counts[_choice_outcome_signature(terminal)] == 1:
                terminal, relays = choice, []
            outcome_groups.setdefault(_choice_outcome_signature(terminal), []).append(
                (choice, terminal, relays))
        canonical_choices[menu_key] = []
        for group in outcome_groups.values():
            group.sort(key=lambda route: (
                route[0].multi_answer_index if route[0].multi_answer_index is not None else -1,
                route[0].reference,
            ))
            terminals = [route[1] for route in group]
            terminals.sort(key=lambda value: (
                value.multi_answer_index if value.multi_answer_index is not None else -1,
                value.reference,
            ))
            canonical = terminals[0]
            canonical_choices[menu_key].append(canonical)
            details[canonical.reference]["choiceAlternatives"].extend(
                choice_route_alternative(entry, terminal, relays)
                for entry, terminal, relays in group
            )
            for entry, terminal, relays in group:
                for alias in [entry, terminal, *relays]:
                    if alias.reference != canonical.reference:
                        aliases[alias.reference] = canonical.reference
        canonical_choices[menu_key].sort(key=lambda value: (
            value.multi_answer_index if value.multi_answer_index is not None else -1,
            value.reference,
        ))

    def resolve_alias(reference: str) -> str:
        while reference in aliases:
            reference = aliases[reference]
        return reference

    # Several menu answers can invoke the same CustomFunctionEvent.  The
    # function's reward/state effects are one executable outcome, not one new
    # outcome per caller.  Collapse summaries that contain the exact same
    # concrete reward nodes and progression effects, while retaining every
    # calling answer as provenance in the detail panel.  This notably prevents
    # Horadric's shared "Drop letter to BS" function from showing the letter
    # once for the dialogue answer and a second time for "Leave".
    shared_callable_groups: dict[tuple[str, tuple[str, ...], str], list[QuestSummary]] = {}
    for summary in included:
        if not summary.multi_answer or not summary.reward_nodes:
            continue
        key = (
            summary.graph,
            tuple(sorted(summary.reward_nodes)),
            _choice_outcome_signature(summary),
        )
        shared_callable_groups.setdefault(key, []).append(summary)
    for duplicates in shared_callable_groups.values():
        roots = sorted({resolve_alias(value.reference) for value in duplicates})
        distinct_answers = {value.multi_answer for value in duplicates}
        if len(roots) < 2 or len(distinct_answers) < 2:
            continue
        canonical = roots[0]
        variants = sorted(duplicates, key=lambda value: (
            value.multi_answer_index if value.multi_answer_index is not None else -1,
            value.reference,
        ))
        existing_variant_ids = {
            value.get("id") for value in details[canonical]["choiceAlternatives"]
        }
        details[canonical]["choiceAlternatives"].extend(
            _choice_alternative(value) for value in variants
            if value.reference not in existing_variant_ids
        )
        details[canonical]["multiAnswerNodes"] = sorted({
            value.multi_answer_node for value in variants
            if value.multi_answer_node is not None
        }, key=lambda value: (not value.isdigit(), int(value) if value.isdigit() else value))
        for duplicate in roots[1:]:
            aliases[duplicate] = canonical

    # FlowCanvas may offer the exact same phrase through several MultiAnswer
    # menus and wire those options to the same executable branch. Keep one
    # domain finding while retaining every source menu as provenance.
    duplicate_groups: dict[tuple[str, str], list[QuestSummary]] = {}
    for summary in included:
        if summary.multi_answer:
            duplicate_groups.setdefault(
                (summary.graph, _duplicate_finding_signature(summary)), []).append(summary)
    for duplicates in duplicate_groups.values():
        roots = sorted({resolve_alias(value.reference) for value in duplicates})
        if len(roots) < 2:
            continue
        canonical = roots[0]
        menus = sorted({
            value.multi_answer_node for value in duplicates
            if value.multi_answer_node is not None
        }, key=lambda value: (not value.isdigit(), int(value) if value.isdigit() else value))
        details[canonical]["multiAnswerNodes"] = menus
        for duplicate in roots[1:]:
            aliases[duplicate] = canonical

    def canonical_reference(reference: str) -> str:
        return resolve_alias(reference)

    # A shared junction represents the MultiAnswer itself. This avoids drawing a
    # Cartesian product when several paths converge on the same revisitable menu.
    for (graph_name, menu_id), predecessors in sorted(menu_predecessors.items()):
        menu_node_id = f"choice-menu:{graph_name}:{menu_id}"
        menu_data = _choice_menu_data(graph_name, menu_id)
        details[menu_node_id] = menu_data
        nodes.append({
            "id": menu_node_id,
            "label": f"choice menu {menu_id}",
            "title": _tooltip(menu_data),
            "group": "choice_menu",
            "graph": graph_name,
            "value": 1,
            "search": json.dumps(menu_data, ensure_ascii=False).casefold(),
        })
        for predecessor in sorted({canonical_reference(value) for value in predecessors}):
            label = "continues to choices"
            key = predecessor, menu_node_id, label
            if key not in edge_keys:
                edge_keys.add(key)
                edges.append({
                    "id": f"edge:{len(edges)}", "from": predecessor, "to": menu_node_id,
                    "label": label, "title": html.escape(f"Flow_MultiAnswer {menu_id}"),
                    "arrows": "to", "kind": "choice_menu",
                })
            details[predecessor]["choiceLinks"].append({
                "direction": "continues", "other": menu_node_id,
                "menu": menu_id, "option": None, "phrase": "choice menu",
            })
            menu_data["choiceLinks"].append({
                "direction": "follows", "other": predecessor,
                "menu": menu_id, "option": None, "phrase": "previous outcome",
            })
        for canonical in canonical_choices[(graph_name, menu_id)]:
            canonical_id = canonical_reference(canonical.reference)
            alternatives = details[canonical.reference]["choiceAlternatives"]
            phrases = [value["phrase"] for value in alternatives]
            normalized = [
                phrase[1:] if phrase.startswith("@") else phrase for phrase in phrases
            ]
            choice_label = " / ".join(normalized)
            if len(choice_label) > 80:
                choice_label = f"{normalized[0]} (+{len(normalized) - 1} alternatives)"
            label = f"answer: {choice_label}"
            key = menu_node_id, canonical_id, label
            if key in edge_keys:
                continue
            edge_keys.add(key)
            edges.append({
                "id": f"edge:{len(edges)}", "from": menu_node_id, "to": canonical_id,
                "label": label, "title": html.escape(
                    f"Flow_MultiAnswer {menu_id}: {' / '.join(phrases)}"),
                "arrows": "to", "kind": "choice_option",
            })
            menu_data["choiceLinks"].append({
                "direction": "offers", "other": canonical_id,
                "menu": menu_id, "option": canonical.multi_answer_index,
                "phrase": " / ".join(phrases),
            })
            details[canonical_id]["choiceLinks"].append({
                "direction": "offered by", "other": menu_node_id,
                "menu": menu_id, "option": canonical.multi_answer_index,
                "phrase": " / ".join(phrases),
            })

    for bridge in _state_event_bridges(analyses, included, unlock_owners):
        label = f"{bridge['parameter']} → {bridge['interactionEvent']}"
        title = (f"SetWGOParam {bridge['setter']}: {bridge['parameter']}={bridge['value']}<br>"
                 f"Flag path: {bridge['flagPath']} ({bridge['check']})<br>"
                 f"Interaction event: {bridge['interactionEvent']}<br>"
                 f"Event path: {bridge['eventPath']}")
        key = bridge["from"], bridge["to"], label
        if key in edge_keys:
            continue
        edge_keys.add(key)
        edges.append({
            "id": f"edge:{len(edges)}", "from": bridge["from"], "to": bridge["to"],
            "label": label, "title": title, "arrows": "to", "kind": "state_event",
            "dashes": True,
        })
        source_link = {**bridge, "direction": "enables"}
        target_link = {**bridge, "direction": "requires"}
        details[bridge["from"]]["stateEventLinks"].append(source_link)
        details[bridge["to"]]["stateEventLinks"].append(target_link)
        details[bridge["to"]]["uncertainties"] = [
            issue for issue in details[bridge["to"]]["uncertainties"]
            if issue != "Flow_UnlockPhrase could not be assigned to a reward/blacklist finding"
        ]

    checked_player_parameters: set[str] = set()
    for owner, (owner_graph_name, _) in owner_nodes.items():
        owner_graph = graph_lookup[owner_graph_name]
        for source_node_id, _, _ in owner_steps.get(owner, set()):
            checker = owner_graph.nodes[source_node_id]
            if checker.type_name not in {
                "Flow_PlayerFlag", "Flow_PlayerParamCompare", "Flow_PlayerParamCompareInt",
            }:
                continue
            parameter = _input(checker, "param", "Param name")
            if isinstance(parameter, str):
                checked_player_parameters.add(parameter)
    owned_graph_nodes = {}
    for owner_graph_name, owned_nodes in owner_nodes.values():
        owned_graph_nodes.setdefault(owner_graph_name, set()).update(owned_nodes)
    for graph in graph_lookup.values():
        for node in graph.nodes.values():
            if (node.type_name not in {"Flow_SetPlayerParam", "Flow_AddPlayerParam"}
                    or node.id in owned_graph_nodes.get(graph.name, set())):
                continue
            parameter = _input(node, "Param name", "param")
            if parameter not in checked_player_parameters:
                continue
            reference = f"player-state-source:{graph.name}.json:{node.id}"
            operation = "sets" if node.type_name == "Flow_SetPlayerParam" else "adds"
            add_bridge_owner(reference, graph, node.id, f"{operation} {parameter}")

    for bridge in _player_state_bridges(analyses, owner_nodes, owner_steps):
        relation = "sets" if bridge["certainty"] == "satisfies" else "contributes to"
        label = f"{bridge['parameter']} ({relation})"
        title = (f"{bridge['setter']} {bridge['operation']} {bridge['parameter']}={bridge['value']}<br>"
                 f"{bridge['check']}")
        key = bridge["from"], bridge["to"], label
        if key in edge_keys:
            continue
        edge_keys.add(key)
        edges.append({
            "id": f"edge:{len(edges)}", "from": bridge["from"], "to": bridge["to"],
            "label": label, "title": title, "arrows": "to", "kind": "player_state",
            "dashes": True,
        })
        details[bridge["from"]]["playerStateLinks"].append({**bridge, "direction": "provides"})
        details[bridge["to"]]["playerStateLinks"].append({**bridge, "direction": "requires"})

    # Match explicit event producers to CustomEvent entry points. Cross-graph
    # matching is restricted to event names that identify exactly one target
    # graph; common names such as "intro" and "interaction" remain unlinked
    # unless producer and receiver are in the same graph.
    custom_event_graphs: dict[str, set[str]] = {}
    for graph in graph_lookup.values():
        for node in graph.nodes.values():
            if node.type_name == "CustomEvent" and _event_name(node):
                custom_event_graphs.setdefault(_event_name(node) or "", set()).add(graph.name)

    event_targets: dict[tuple[str, str], set[str]] = {}
    for target, (target_graph_name, target_node_ids) in owner_nodes.items():
        target_graph = graph_lookup[target_graph_name]
        for target_node_id in target_node_ids:
            target_node = target_graph.nodes[target_node_id]
            if target_node.type_name == "CustomEvent" and _event_name(target_node):
                event_targets.setdefault(
                    (target_graph_name, _event_name(target_node) or ""), set()).add(target)

    owned_graph_nodes = {}
    for owner_graph_name, owned_nodes in owner_nodes.values():
        owned_graph_nodes.setdefault(owner_graph_name, set()).update(owned_nodes)
    for graph in graph_lookup.values():
        for node in graph.nodes.values():
            emitted = _emitted_event(node)
            if emitted is None or node.id in owned_graph_nodes.get(graph.name, set()):
                continue
            event, kind = emitted
            target_graphs = custom_event_graphs.get(event, set())
            explicit_targets = _event_wgo_graphs(node, graph, graph_lookup)
            can_target = bool(target_graphs.intersection(explicit_targets)) if explicit_targets else (
                graph.name in target_graphs or len(target_graphs) == 1)
            if not target_graphs or not can_target:
                continue
            reference = f"event-source:{graph.name}.json:{node.id}"
            add_bridge_owner(reference, graph, node.id, f"{kind} {event}")

    for source, (source_graph_name, source_node_ids) in list(owner_nodes.items()):
        source_graph = graph_lookup[source_graph_name]
        for source_node_id in source_node_ids:
            emitted = _emitted_event(source_graph.nodes[source_node_id])
            if emitted is None:
                continue
            specific_owner = f"event-source:{source_graph_name}.json:{source_node_id}"
            if specific_owner in owner_nodes and source != specific_owner:
                continue
            event, kind = emitted
            target_graphs = custom_event_graphs.get(event, set())
            explicit_targets = _event_wgo_graphs(
                source_graph.nodes[source_node_id], source_graph, graph_lookup)
            if explicit_targets:
                candidate_graphs = target_graphs.intersection(explicit_targets)
            elif source_graph_name in target_graphs:
                candidate_graphs = {source_graph_name}
            elif len(target_graphs) == 1:
                candidate_graphs = target_graphs
            else:
                continue
            for target_graph_name in candidate_graphs:
                for target in event_targets.get((target_graph_name, event), set()):
                    if source == target:
                        continue
                    label = f"{kind}: {event}"
                    key = source, target, label
                    if key in edge_keys:
                        continue
                    edge_keys.add(key)
                    link = {
                        "from": source, "to": target, "event": event, "kind": kind,
                        "sourceNode": source_node_id, "sourceGraph": source_graph_name,
                        "targetGraph": target_graph_name,
                    }
                    edges.append({
                        "id": f"edge:{len(edges)}", "from": source, "to": target,
                        "label": label,
                        "title": html.escape(
                            f"{source_graph.nodes[source_node_id].type_name} "
                            f"{source_graph_name}.json:{source_node_id} → "
                            f"{target_graph_name}.CustomEvent({event})"),
                        "arrows": "to", "kind": "event", "dashes": True,
                    })
                    details[source]["eventLinks"].append({**link, "direction": "emits"})
                    details[target]["eventLinks"].append({**link, "direction": "receives"})

    # Flow_RunScript invokes another FlowGraph by name. Link the caller to every
    # included finding whose execution path begins at the target graph's
    # StartEvent; this models the actual GS.RunFlowScript boundary without
    # attaching unrelated CustomEvent-only branches from the same file.
    for source, (source_graph_name, source_node_ids) in owner_nodes.items():
        source_graph = graph_lookup[source_graph_name]
        for call in _run_script_calls(source_graph, source_node_ids):
            specific_owner = f"script-call:{source_graph_name}.json:{call['node']}"
            if specific_owner in owner_nodes and source != specific_owner:
                continue
            target_graph_name = _script_graph_name(call["script"], graph_lookup)
            if target_graph_name is None:
                continue
            target_graph = graph_lookup[target_graph_name]
            start_nodes = {
                node.id for node in target_graph.nodes.values()
                if node.type_name == "StartEvent"
            }
            for target, (owner_graph_name, target_node_ids) in owner_nodes.items():
                if owner_graph_name != target_graph_name or not start_nodes.intersection(target_node_ids):
                    continue
                label = f"runs {call['script']}"
                key = source, target, label
                if source == target or key in edge_keys:
                    continue
                edge_keys.add(key)
                link = {
                    "from": source, "to": target, "script": call["script"],
                    "callNode": call["node"], "targetGraph": target_graph_name,
                }
                edges.append({
                    "id": f"edge:{len(edges)}", "from": source, "to": target,
                    "label": label,
                    "title": html.escape(
                        f"Flow_RunScript {source_graph_name}.json:{call['node']} "
                        f"→ {target_graph_name}.StartEvent"),
                    "arrows": "to", "kind": "run_script", "dashes": True,
                })
                details[source]["scriptLinks"].append({**link, "direction": "calls"})
                details[target]["scriptLinks"].append({**link, "direction": "entered by"})

    _apply_node_aliases(nodes, details, edges, aliases)
    internal_incoming = {
        edge["to"] for edge in edges if edge.get("kind") != "game_data"
    }
    edges[:] = [
        edge for edge in edges
        if edge.get("kind") != "game_data" or edge["to"] not in internal_incoming
    ]
    connected = {endpoint for edge in edges for endpoint in (edge["from"], edge["to"])}
    unused_bridges = {
        node["id"] for node in nodes
        if node["group"] == "bridge" and node["id"] not in connected
    }
    if unused_bridges:
        nodes[:] = [node for node in nodes if node["id"] not in unused_bridges]
        for node_id in unused_bridges:
            details.pop(node_id, None)
    for node in nodes:
        is_debug = _is_debug_node(node["graph"], node["id"])
        node["isDebug"] = is_debug
        details[node["id"]]["isDebug"] = is_debug
    for node in nodes:
        data = details[node["id"]]
        alternatives = data.get("choiceAlternatives", [])
        if len(alternatives) > 1:
            first = alternatives[0]["phrase"].removeprefix("@")
            node["label"] = f"{first} (+{len(alternatives) - 1} alternatives)"
    content_pack_counts = _assign_content_packs(nodes, details, edges)
    _add_item_requirement_edges(nodes, details, edges)
    _add_start_node(nodes, details, edges)
    node_pack_before_pruning = {
        node["id"]: node["contentPack"] for node in nodes
    }
    for node_id in _prune_navigation_only_leaves(nodes, details, edges):
        content_pack_counts[node_pack_before_pruning[node_id]] -= 1

    incoming = {edge["to"] for edge in edges}
    for node in nodes:
        data = details[node["id"]]
        if node["group"] == "reward" and node["id"] not in incoming:
            data["unresolvedEntry"] = True
            warning = "Ausführungseinstieg nicht aufgelöst; Reward bleibt sichtbar"
            if warning not in data["uncertainties"]:
                data["uncertainties"].append(warning)
            node["title"] = _tooltip(data)
            node["search"] = json.dumps(data, ensure_ascii=False).casefold()

    node_names = node_names or {}
    for node in nodes:
        data = details[node["id"]]
        technical_name = node["label"]
        display_name = node_names.get(node["id"], technical_name)
        data["technicalName"] = technical_name
        data["displayName"] = display_name
        node["label"] = display_name
        node["title"] = _tooltip(data)
        node["search"] = json.dumps(data, ensure_ascii=False).casefold()

    lanes = _assign_directed_layout(nodes, edges)
    # Filtering and alias consolidation can leave gaps in the earlier sequence.
    # Reassign IDs only after every edge has been added so vis.DataSet never sees
    # a newly appended edge reuse an existing numeric ID.
    for edge_index, edge in enumerate(edges):
        edge["id"] = f"edge:{edge_index}"

    return {
        "nodes": nodes, "edges": edges, "details": details,
        "lanes": lanes,
        "stats": {"nodes": len(nodes), "edges": len(edges), "phrases": len(unlockers),
                  "contentPacks": content_pack_counts},
    }


def render_quest_graph_html(data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Graveyard Keeper Quest Graph</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.2/dist/dist/vis-network.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.2/dist/vis-network.min.js"></script>
<style>
:root {{ color-scheme: light dark; --bg:#11151b; --panel:#191f27; --text:#eef3f8; --muted:#a9b4c0; --border:#34404d; --accent:#5eb5ff; --reward:#3178c6; --phrase:#8b5cf6; --unlock:#2f9e67; }}
* {{ box-sizing:border-box; }}
html,body {{ height:100%; margin:0; font:14px system-ui,sans-serif; background:var(--bg); color:var(--text); overflow:hidden; }}
#app {{ height:100%; display:grid; grid-template-rows:auto 1fr; }}
header {{ display:flex; gap:12px; align-items:end; padding:12px 16px; border-bottom:1px solid var(--border); background:var(--panel); flex-wrap:wrap; }}
label,.filter-field {{ display:grid; gap:4px; color:var(--muted); }}
input,select,button {{ font:inherit; color:var(--text); background:var(--bg); border:1px solid var(--border); border-radius:5px; padding:8px 10px; }}
input {{ width:min(420px,70vw); }} button {{ background:var(--reward); border-color:var(--reward); }}
.toggle {{ display:flex; align-items:center; gap:8px; min-height:36px; padding:0 3px; color:var(--text); cursor:pointer; }}
.toggle input {{ width:16px; height:16px; margin:0; padding:0; accent-color:var(--accent); }}
.multi-select {{ position:relative; min-width:190px; color:var(--text); }}
.multi-select summary {{ min-height:36px; max-width:280px; padding:8px 32px 8px 10px; border:1px solid var(--border); border-radius:5px; background:var(--bg); cursor:pointer; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; list-style:none; }}
.multi-select summary::-webkit-details-marker {{ display:none; }}
.multi-select summary::after {{ content:'▾'; position:absolute; right:11px; top:9px; color:var(--muted); }}
.multi-select[open] summary {{ border-color:var(--accent); }}
.multi-select[open] summary::after {{ content:'▴'; }}
.checkbox-menu {{ position:absolute; z-index:100; top:calc(100% + 4px); left:0; width:max(100%,280px); max-width:min(440px,calc(100vw - 32px)); max-height:360px; overflow:auto; padding:6px; border:1px solid var(--border); border-radius:7px; background:var(--panel); box-shadow:0 12px 36px #0009; }}
.checkbox-menu label {{ display:flex; align-items:flex-start; gap:9px; padding:7px 8px; border-radius:4px; color:var(--text); cursor:pointer; overflow-wrap:anywhere; }}
.checkbox-menu label[hidden] {{ display:none; }}
.checkbox-menu label:hover {{ background:#ffffff12; }}
.checkbox-menu input[type=checkbox] {{ flex:0 0 auto; width:16px; height:16px; margin:2px 0 0; padding:0; accent-color:var(--accent); }}
.checkbox-menu .select-all {{ position:sticky; top:-6px; z-index:1; border-bottom:1px solid var(--border); border-radius:0; background:var(--panel); font-weight:650; }}
.checkbox-menu .option-search {{ position:sticky; top:-6px; z-index:2; width:calc(100% - 8px); margin:0 4px 5px; padding:7px 9px; background:var(--bg); }}
.multi-select.has-search .select-all {{ top:36px; }}
.checkbox-options:empty::after,.checkbox-options.no-matches::after {{ content:'No matching entries'; display:block; padding:10px 8px; color:var(--muted); }}
#status {{ margin-left:auto; color:var(--muted); padding:8px 0; }}
.layout-note {{ width:100%; color:var(--muted); font-size:12px; }}
.graph-navigation {{ width:100%; display:flex; align-items:center; gap:7px; flex-wrap:wrap; padding:7px 9px; border:1px solid var(--border); border-radius:7px; background:#0002; color:var(--muted); font-size:12px; }}
.graph-navigation button {{ padding:5px 9px; border-color:#d6a11d; background:#3a321d; color:#ffe9a8; font-size:12px; }}
.graph-navigation button:hover {{ border-color:#ffe08a; background:#4a4024; }}
main {{ min-height:0; display:grid; grid-template-columns:minmax(0,1fr) 380px; }}
#network {{ min-width:0; min-height:0; background:var(--bg); }}
#loading-overlay {{ position:fixed; inset:0; z-index:1000; display:grid; place-items:center; background:rgba(17,21,27,.96); }}
#loading-overlay[hidden] {{ display:none; }}
.loading-card {{ width:min(460px,calc(100vw - 32px)); padding:24px; border:1px solid var(--border); border-radius:10px; background:var(--panel); box-shadow:0 16px 60px #0008; }}
.loading-card strong,.loading-card span {{ display:block; }}
.loading-card strong {{ margin-bottom:12px; font-size:18px; }}
.loading-card progress {{ width:100%; height:18px; margin:8px 0 10px; accent-color:var(--accent); }}
.loading-card.error {{ border-color:#d95c5c; }}
.loading-card.error progress {{ display:none; }}
aside {{ overflow:auto; border-left:1px solid var(--border); background:var(--panel); padding:16px; }}
h1 {{ font-size:18px; margin:0 16px 0 0; }} h2 {{ font-size:17px; overflow-wrap:anywhere; }} h3 {{ font-size:14px; margin:18px 0 6px; color:var(--muted); }}
ul {{ margin:6px 0; padding-left:20px; }} li {{ margin:4px 0; overflow-wrap:anywhere; }}
.empty {{ color:var(--muted); }} .reward {{ border-left:3px solid var(--reward); padding-left:9px; }}
code {{ overflow-wrap:anywhere; color:var(--accent); }}
@media(max-width:800px) {{ main {{ grid-template-columns:1fr; grid-template-rows:minmax(420px,60vh) auto; overflow:auto; }} aside {{ border-left:0; border-top:1px solid var(--border); }} html,body,#app {{ min-height:100%; height:auto; overflow:auto; }} #network {{ height:60vh; }} #status {{ width:100%; margin:0; }} }}
</style>
</head>
<body>
<div id="loading-overlay" role="status" aria-live="polite">
  <div class="loading-card" id="loading-card">
    <strong id="loading-title">Quest graph wird geladen…</strong>
    <progress id="loading-progress" max="100" value="0"></progress>
    <span id="loading-message">HTML und Bibliothek werden vorbereitet…</span>
  </div>
</div>
<div id="app">
<header>
  <h1>Quest graph</h1>
  <label>Search<input id="search" type="search" placeholder="Phrase, NPC, item, conversation…"></label>
  <div class="filter-field"><span>Content</span><details class="multi-select" id="content-pack"><summary>All content</summary><div class="checkbox-menu"><label class="select-all"><input type="checkbox">Select all</label><div class="checkbox-options"></div></div></details></div>
  <div class="filter-field"><span>Graph</span><details class="multi-select has-search" id="graph"><summary>All graphs</summary><div class="checkbox-menu"><input class="option-search" type="search" placeholder="Search graphs…" aria-label="Search graph options"><label class="select-all"><input type="checkbox">Select all</label><div class="checkbox-options"></div></div></details></div>
  <div class="filter-field"><span>Matching node</span><details class="multi-select has-search" id="node-list"><summary>Select nodes</summary><div class="checkbox-menu"><input class="option-search" type="search" placeholder="Search matching nodes…" aria-label="Search matching node options"><label class="select-all"><input type="checkbox">Select all</label><div class="checkbox-options"></div></div></details></div>
  <label class="toggle"><input id="show-debug" type="checkbox">Show debug/test nodes</label>
  <button id="fit" type="button">Fit graph</button>
  <span id="status" aria-live="polite"></span>
  <div class="graph-navigation" id="graph-navigation" aria-live="polite"></div>
  <div class="layout-note">Reading direction: left → right by dependency depth. Visible depth columns and content lanes are compacted dynamically. Use + boundary nodes to include connected graphs and − Collapse chips to hide them again.</div>
</header>
<main><div id="network" role="img" aria-label="Directed quest graph"></div>
<aside id="detail"><p class="empty">Select a node to see all extracted details.</p></aside></main>
</div>
<script>
const graphData={payload};
const loadingOverlay=document.getElementById('loading-overlay');
const loadingCard=document.getElementById('loading-card');
const loadingTitle=document.getElementById('loading-title');
const loadingProgress=document.getElementById('loading-progress');
const loadingMessage=document.getElementById('loading-message');
const nextPaint=()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
function setLoading(percent,message){{loadingProgress.value=percent;loadingMessage.textContent=`${{percent}}% · ${{message}}`;}}
async function initializeGraph(){{
setLoading(10,`${{graphData.stats.nodes}} Knoten und ${{graphData.stats.edges}} Kanten gelesen`);
await nextPaint();
const allNodes=graphData.nodes, allEdges=graphData.edges, details=graphData.details;
setLoading(25,'Layout-Bahnen vorbereitet');
await nextPaint();
const nodes=new vis.DataSet(), edges=new vis.DataSet();
setLoading(45,'Graph-Datensätze aufgebaut');
await nextPaint();
const network=new vis.Network(document.getElementById('network'),{{nodes,edges}},{{
  interaction:{{hover:true,navigationButtons:true,keyboard:true}},
  nodes:{{shape:'dot',font:{{color:'#eef3f8',strokeWidth:3,strokeColor:'#11151b'}},borderWidth:1}},
  edges:{{color:{{color:'#66788a',highlight:'#5eb5ff'}},font:{{color:'#a9b4c0',strokeWidth:3,strokeColor:'#11151b',size:10}},smooth:{{type:'cubicBezier',forceDirection:'horizontal',roundness:.35}}}},
  groups:{{reward:{{color:{{background:'#3178c6',border:'#79b8f3'}}}},phrase:{{color:{{background:'#8b5cf6',border:'#bba2ff'}}}},unlock:{{shape:'diamond',color:{{background:'#2f9e67',border:'#72d6a8'}}}},bridge:{{shape:'diamond',color:{{background:'#a56822',border:'#e4ad68'}}}},choice_menu:{{shape:'box',color:{{background:'#56616d',border:'#a9b4c0'}}}},start:{{shape:'star',size:28,color:{{background:'#d6a11d',border:'#ffe08a'}}}},graph_expander:{{shape:'box',font:{{color:'#ffe9a8'}},color:{{background:'#3a321d',border:'#d6a11d'}},borderWidth:2,margin:10}},content_anchor:{{shape:'box',font:{{size:22,color:'#eef3f8'}},color:{{background:'#252d37',border:'#a9b4c0'}},borderWidth:2,margin:14}}}},
  physics:false
}});
setLoading(65,'Interaktive Ansicht initialisiert');
await nextPaint();
const search=document.getElementById('search'), pack=document.getElementById('content-pack'), graph=document.getElementById('graph'), nodeList=document.getElementById('node-list'), showDebug=document.getElementById('show-debug'), status=document.getElementById('status'), graphNavigation=document.getElementById('graph-navigation');
const nodeById=new Map(allNodes.map(node=>[node.id,node]));
const contentEntries=graphData.lanes.map(lane=>({{value:lane.name,label:`${{lane.name}} (${{graphData.stats.contentPacks[lane.name]??0}})`}}));
const graphEntries=[...new Set(allNodes.map(n=>n.graph))].sort().map(name=>({{value:name,label:name}}));
const STORAGE_KEY='graveyard-keeper-quest-graph-state-v1';
let stateReady=false,persistTimer=null,pendingMatchingSelection=null;
function loadSavedState(){{
  try{{const value=JSON.parse(localStorage.getItem(STORAGE_KEY)??'null');return value?.version===1?value:{{}};}}
  catch(error){{console.warn('Quest graph state could not be restored.',error);return {{}};}}
}}
const savedState=loadSavedState();
function savedChecklistValues(entries,key){{
  const valid=new Set(entries.map(entry=>entry.value)),saved=savedState[key];
  return Array.isArray(saved)?new Set(saved.filter(value=>valid.has(value))):new Set(valid);
}}
function validSavedView(value){{
  const x=value?.position?.x,y=value?.position?.y,scale=value?.scale;
  return Number.isFinite(x)&&Number.isFinite(y)&&Number.isFinite(scale)&&scale>0?{{position:{{x,y}},scale}}:null;
}}
function persistState(){{
  if(!stateReady)return;
  const graphOptionSearch=graph.querySelector('.option-search'),nodeOptionSearch=nodeList.querySelector('.option-search');
  try{{localStorage.setItem(STORAGE_KEY,JSON.stringify({{
    version:1,search:search.value,
    contentPacks:[...checklistValues(pack)],graphs:[...checklistValues(graph)],matchingNodes:[...checklistValues(nodeList)],
    showDebug:showDebug.checked,
    graphOptionSearch:graphOptionSearch?.value??'',nodeOptionSearch:nodeOptionSearch?.value??'',
    view:{{position:network.getViewPosition(),scale:network.getScale()}},
    selection:{{nodes:network.getSelectedNodes(),edges:network.getSelectedEdges()}}
  }}));}}
  catch(error){{console.warn('Quest graph state could not be saved.',error);}}
}}
function schedulePersist(){{
  if(!stateReady)return;
  clearTimeout(persistTimer);persistTimer=setTimeout(persistState,120);
}}
function checklistInputs(control){{return [...control.querySelectorAll('.checkbox-options input[type=checkbox]')];}}
function visibleChecklistInputs(control){{return checklistInputs(control).filter(input=>!input.closest('label').hidden);}}
function checklistValues(control){{return new Set(checklistInputs(control).filter(input=>input.checked).map(input=>input.value));}}
function refreshChecklist(control,notify=false){{
  const inputs=checklistInputs(control),selected=inputs.filter(input=>input.checked),visibleInputs=visibleChecklistInputs(control),visibleSelected=visibleInputs.filter(input=>input.checked);
  const selectAll=control.querySelector('.select-all input');
  selectAll.checked=visibleInputs.length>0&&visibleSelected.length===visibleInputs.length;
  selectAll.indeterminate=visibleSelected.length>0&&visibleSelected.length<visibleInputs.length;
  const summary=control.querySelector('summary');
  if(selected.length===inputs.length&&inputs.length)summary.textContent=control.dataset.allLabel;
  else if(!selected.length)summary.textContent=control.dataset.emptyLabel;
  else if(selected.length===1)summary.textContent=selected[0].dataset.label;
  else summary.textContent=`${{selected.length}} selected`;
  if(notify&&control._onChange)control._onChange();
}}
function filterChecklistOptions(control){{
  const optionSearch=control.querySelector('.option-search'),term=(optionSearch?.value??'').trim().toLocaleLowerCase();
  checklistInputs(control).forEach(input=>input.closest('label').hidden=Boolean(term)&&!input.dataset.label.toLocaleLowerCase().includes(term));
  control.querySelector('.checkbox-options').classList.toggle('no-matches',visibleChecklistInputs(control).length===0&&checklistInputs(control).length>0);
  refreshChecklist(control,false);
}}
function setChecklistOptions(control,entries,selectedValues,allLabel,emptyLabel,onChange){{
  control.dataset.allLabel=allLabel;control.dataset.emptyLabel=emptyLabel;control._onChange=onChange;
  const options=control.querySelector('.checkbox-options');options.replaceChildren();
  entries.forEach(entry=>{{
    const label=document.createElement('label'),input=document.createElement('input'),text=document.createElement('span');
    input.type='checkbox';input.value=entry.value;input.checked=selectedValues.has(entry.value);input.dataset.label=entry.label;
    input.addEventListener('change',()=>refreshChecklist(control,true));
    text.textContent=entry.label;label.append(input,text);options.append(label);
  }});
  const selectAll=control.querySelector('.select-all input');
  selectAll.onchange=()=>{{visibleChecklistInputs(control).forEach(input=>input.checked=selectAll.checked);refreshChecklist(control,true);}};
  const optionSearch=control.querySelector('.option-search');if(optionSearch)optionSearch.oninput=()=>{{filterChecklistOptions(control);schedulePersist();}};
  filterChecklistOptions(control);
}}
search.value=typeof savedState.search==='string'?savedState.search:'';
showDebug.checked=savedState.showDebug===true;
graph.querySelector('.option-search').value=typeof savedState.graphOptionSearch==='string'?savedState.graphOptionSearch:'';
nodeList.querySelector('.option-search').value=typeof savedState.nodeOptionSearch==='string'?savedState.nodeOptionSearch:'';
pendingMatchingSelection=Array.isArray(savedState.matchingNodes)?new Set(savedState.matchingNodes):null;
setChecklistOptions(pack,contentEntries,savedChecklistValues(contentEntries,'contentPacks'),'All content','No content',applyFilter);
setChecklistOptions(graph,graphEntries,savedChecklistValues(graphEntries,'graphs'),'All graphs','No graphs',applyFilter);
setChecklistOptions(nodeList,[],new Set(),'All matching nodes','Select nodes',handleNodeSelection);
function handleNodeSelection(){{
  const selected=[...checklistValues(nodeList)].filter(id=>nodes.get(id));
  network.selectNodes(selected);
  if(selected.length===1){{network.focus(selected[0],{{scale:1.15,animation:true}});showDetail(selected[0]);}}
  schedulePersist();
}}
function setGraphIncluded(graphName,included){{
  const input=checklistInputs(graph).find(entry=>entry.value===graphName);
  if(!input)return;
  const preservedView={{position:network.getViewPosition(),scale:network.getScale()}};
  input.checked=included;refreshChecklist(graph,false);applyFilter(preservedView);
}}
function updateGraphNavigation(selectedGraphs){{
  graphNavigation.replaceChildren();
  const label=document.createElement('span');
  if(selectedGraphs.size===graphEntries.length){{label.textContent='All graphs included';graphNavigation.append(label);return;}}
  if(!selectedGraphs.size){{label.textContent='No graphs included';graphNavigation.append(label);return;}}
  label.textContent='Included graphs:';graphNavigation.append(label);
  [...selectedGraphs].sort().forEach(graphName=>{{
    const button=document.createElement('button');button.type='button';button.textContent=`− Collapse ${{graphName}}`;
    button.title=`Collapse ${{graphName}}`;button.addEventListener('click',()=>setGraphIncluded(graphName,false));graphNavigation.append(button);
  }});
}}
function compactVisibleLayout(visible,layoutHelpers=[]){{
  const layoutNodes=[...visible,...layoutHelpers];
  const layoutDepth=node=>node.layoutDepth??node.depth;
  const visibleDepths=[...new Set(layoutNodes.map(layoutDepth))].sort((a,b)=>a-b);
  const depthColumn=new Map(visibleDepths.map((depth,index)=>[depth,index]));
  const positions=new Map(),positioned=[],anchors=[];
  let laneTop=0;
  graphData.lanes.map(lane=>lane.name).forEach(packName=>{{
    const packNodes=layoutNodes.filter(node=>node.contentPack===packName);
    if(!packNodes.length)return;
    const buckets=new Map();
    packNodes.forEach(node=>{{const column=depthColumn.get(layoutDepth(node));if(!buckets.has(column))buckets.set(column,[]);buckets.get(column).push(node);}});
    const largestBucket=Math.max(...[...buckets.values()].map(values=>values.length));
    const laneHeight=Math.max(340,largestBucket*92+140),laneCenter=laneTop+laneHeight/2;
    [...buckets.entries()].sort((a,b)=>a[0]-b[0]).forEach(([column,values])=>{{
      values.sort((a,b)=>(a.layoutRank??1)-(b.layoutRank??1)||(a.layoutOrder??a.label).localeCompare(b.layoutOrder??b.label)||a.id.localeCompare(b.id));
      values.forEach((node,index)=>{{
        const position={{x:column*310,y:laneCenter+(index-(values.length-1)/2)*92}};
        positions.set(node.id,position);positioned.push({{...node,...position}});
      }});
    }});
    anchors.push({{id:`content-anchor:${{packName}}`,label:packName,x:-360,y:laneCenter,fixed:{{x:true,y:true}},physics:false,group:'content_anchor',contentPack:packName}});
    laneTop+=laneHeight+130;
  }});
  return {{positions,positioned,anchors}};
}}
function applyFilter(preservedView=null){{
  const term=search.value.trim().toLocaleLowerCase(),selectedGraphs=checklistValues(graph),selectedPacks=checklistValues(pack);
  const graphRestricted=selectedGraphs.size<graphEntries.length;
  const seed=allNodes.filter(n=>(showDebug.checked||!n.isDebug)&&selectedGraphs.has(n.graph)&&selectedPacks.has(n.contentPack)&&(!term||n.search.includes(term)));
  const seedIds=new Set(seed.map(n=>n.id));
  const shownEdges=allEdges.filter(edge=>seedIds.has(edge.from)&&seedIds.has(edge.to));
  const boundaryGroups=new Map();
  if(graphRestricted)allEdges.forEach(edge=>{{
    const fromVisible=seedIds.has(edge.from),toVisible=seedIds.has(edge.to);
    if(fromVisible===toVisible)return;
    const visibleId=fromVisible?edge.from:edge.to,externalId=fromVisible?edge.to:edge.from;
    const external=nodeById.get(externalId),visibleNode=nodeById.get(visibleId);
    if(!external||!visibleNode||(!showDebug.checked&&external.isDebug)||selectedGraphs.has(external.graph)||!selectedPacks.has(external.contentPack))return;
    const direction=fromVisible?'out':'in',key=`${{visibleId}}\u0000${{external.graph}}\u0000${{direction}}`;
    const group=boundaryGroups.get(key)??{{visibleId,externalGraph:external.graph,direction,edges:[]}};
    group.edges.push(edge);boundaryGroups.set(key,group);
  }});
  const expanders=[],boundaryEdges=[];
  [...boundaryGroups.values()].sort((a,b)=>a.externalGraph.localeCompare(b.externalGraph)||a.visibleId.localeCompare(b.visibleId)).forEach((group,index)=>{{
    const visibleNode=nodeById.get(group.visibleId),side=group.direction==='out'?1:-1;
    const expanderId=`graph-expander:${{index}}`;
    expanders.push({{id:expanderId,label:`+ ${{group.externalGraph}}`,title:`Include graph ${{group.externalGraph}} (${{group.edges.length}} connection${{group.edges.length===1?'':'s'}})`,group:'graph_expander',expandGraph:group.externalGraph,contentPack:visibleNode.contentPack,graph:group.externalGraph,layoutDepth:visibleNode.depth+side,layoutRank:group.direction==='in'?0:2,layoutOrder:`${{visibleNode.label}}\u0000${{group.externalGraph}}`,physics:false,value:1}});
    const labels=[...new Set(group.edges.map(edge=>edge.label).filter(Boolean))];
    boundaryEdges.push({{id:`collapsed-edge:${{index}}`,from:group.direction==='out'?group.visibleId:expanderId,to:group.direction==='out'?expanderId:group.visibleId,label:group.edges.length===1?(labels[0]||'cross-graph link'):`${{group.edges.length}} cross-graph links`,title:labels.join('\\n'),arrows:'to',kind:'collapsed_graph',dashes:true}});
  }});
  const compactLayout=compactVisibleLayout(seed,expanders);
  shownEdges.push(...boundaryEdges);
  const visible=seed;
  nodes.clear(); nodes.add([...compactLayout.positioned,...compactLayout.anchors]); edges.clear(); edges.add(shownEdges);
  const previousNodeSelection=pendingMatchingSelection??checklistValues(nodeList);pendingMatchingSelection=null;
  const nodeEntries=visible.slice().sort((a,b)=>a.label.localeCompare(b.label)).map(n=>({{value:n.id,label:`${{n.label}} · ${{n.contentPack}} · ${{n.graph}}`}}));
  const retainedSelection=new Set(nodeEntries.filter(entry=>previousNodeSelection.has(entry.value)).map(entry=>entry.value));
  setChecklistOptions(nodeList,nodeEntries,retainedSelection,'All matching nodes','Select nodes',handleNodeSelection);
  handleNodeSelection();
  updateGraphNavigation(selectedGraphs);
  const hiddenDebug=showDebug.checked?0:allNodes.filter(node=>node.isDebug).length;
  status.textContent=`${{visible.length}} nodes · ${{shownEdges.length}} links${{hiddenDebug?` · ${{hiddenDebug}} debug/test nodes hidden`:''}}${{expanders.length?` · ${{expanders.length}} expandable graph boundaries`:''}}`;
  if(preservedView)network.moveTo({{position:preservedView.position,scale:preservedView.scale,animation:false}});
  else if(visible.length||expanders.length)network.fit({{animation:false}});
  schedulePersist();
}}
search.addEventListener('input',()=>applyFilter());
showDebug.addEventListener('change',()=>applyFilter());
document.addEventListener('click',event=>document.querySelectorAll('.multi-select[open]').forEach(control=>{{if(!control.contains(event.target))control.open=false;}}));
document.getElementById('fit').addEventListener('click',()=>network.fit({{animation:true}}));
const esc=value=>String(value??'').replace(/[&<>\"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}}[c]));
const list=(title,items,format=x=>esc(x))=>items?.length?`<h3>${{title}}</h3><ul>${{items.map(x=>`<li>${{format(x)}}</li>`).join('')}}</ul>`:'';
function showDetail(id){{
  const d=details[id]; if(!d)return;
  let out=`<h2>${{esc(d.displayName||d.multiAnswer||d.id)}}</h2><p><strong>${{esc(d.contentPack)}}</strong><br><code>${{esc(d.file)}}</code><br><strong>Original node name:</strong> ${{esc(d.technicalName||d.multiAnswer||d.id)}}<br><small>Stable node ID: <code>${{esc(d.id)}}</code></small></p>`;
  if(d.unresolvedEntry)out+=`<p class="reward"><strong>Entry source unresolved</strong><br>The reward remains visible; only its incoming execution path is still unknown.</p>`;
  out+=list('Available in MultiAnswer menus',d.multiAnswerNodes);
  if(d.rewards.length) out+=`<h3>Rewards</h3>${{d.rewards.map(r=>r.type==='relation'?`<p class="reward"><strong>Relation +${{esc(r.amount)}}</strong><br>NPC: ${{esc(r.npc)}}${{r.npcSource?`<br><small>${{esc(r.npcSource)}}</small>`:''}}</p>`:`<p class="reward"><strong>Item drop</strong><br>${{esc(r.item)}} × ${{esc(r.amount)}}${{r.resolution?`<br><small>${{esc(r.resolution)}}</small>`:''}}</p>`).join('')}}`;
  out+=list('Required quests',d.requiredQuests)+list('Unlock sources',d.requiredQuestSources);
  out+=list('Required happiness',d.requiredHappiness,r=>`${{esc(r.amount)}} with ${{esc(r.npc)}}${{r.npcSource?` <small>(${{esc(r.npcSource)}})</small>`:''}}`);
  out+=list('Required items',d.requiredItems)+list('Costs',d.costs)+list('Other requirements',d.otherRequirements);
  out+=list('Entry events',d.entryEvents);
  out+=list('Player state changes',d.playerStateChanges,c=>`${{esc(c.parameter)}} ${{c.operation==='set'?'=':'+='}} ${{esc(c.value)}} <small>(node ${{esc(c.node)}})</small>`);
  out+=list('Function calls',d.functionCalls);
  out+=list('Conversations',d.conversations)+list('Task states',d.taskStates,t=>`${{esc(t.task)}}: ${{esc(t.state)}}`);
  out+=list('Phrases unlocked',d.phrasesUnlocked)+list('Phrases blacklisted',d.phrasesToBlacklist)+list('Phrases removed from blacklist',d.phrasesRemovedFromBlacklist);
  out+=list('State/event links',d.stateEventLinks,l=>`${{esc(l.direction)}}: ${{esc(l.parameter)}}=${{esc(l.value)}} → ${{esc(l.interactionEvent)}}<br><small>flag path: ${{esc(l.flagPath)}} (${{esc(l.check)}})<br>event path: ${{esc(l.eventPath)}}</small>`);
  out+=list('Player-state links',d.playerStateLinks,l=>`${{esc(l.direction)}}: ${{esc(l.parameter)}} <small>(${{esc(l.setter)}} → ${{esc(l.check)}})</small>`);
  out+=list('Flow script links',d.scriptLinks,l=>`${{esc(l.direction)}}: ${{esc(l.script)}} <small>(Flow_RunScript node ${{esc(l.callNode)}})</small>`);
  out+=list('Event links',d.eventLinks,l=>`${{esc(l.direction)}}: ${{esc(l.event)}} <small>(${{esc(l.kind)}}, node ${{esc(l.sourceNode)}})</small>`);
  out+=list('GameData entry sources',d.externalSources,s=>`${{esc(s.trigger)}} → ${{esc(s.script)}} <small>(${{esc(s.file)}}: ${{esc(s.record)}}.${{esc(s.field)}})</small>`);
  out+=list('Choice continuations',d.choiceLinks,l=>`${{esc(l.direction)}}: ${{esc(l.phrase)}} <small>(MultiAnswer ${{esc(l.menu)}}, option ${{esc(l.option)}})</small>`);
  out+=list('Equivalent answer variants',d.choiceAlternatives,a=>{{
    const facts=[];
    if(a.viaPhrases?.length)facts.push(`via dialogue: ${{a.viaPhrases.map(esc).join(' → ')}}`);
    if(a.costs?.length)facts.push(`costs: ${{a.costs.map(esc).join(', ')}}`);
    if(a.requiredQuests?.length)facts.push(`requires: ${{a.requiredQuests.map(esc).join(', ')}}`);
    if(a.requiredItems?.length)facts.push(`items: ${{a.requiredItems.map(esc).join(', ')}}`);
    if(a.requiredHappiness?.length)facts.push(`happiness: ${{a.requiredHappiness.map(r=>`${{esc(r.amount)}} with ${{esc(r.npc)}}`).join(', ')}}`);
    if(a.otherRequirements?.length)facts.push(`conditions: ${{a.otherRequirements.map(esc).join(', ')}}`);
    if(a.conversations?.length)facts.push(`dialogue: ${{a.conversations.map(esc).join(' → ')}}`);
    if(a.functionCalls?.length)facts.push(`calls: ${{a.functionCalls.map(esc).join(', ')}}`);
    return `<strong>${{esc(a.phrase)}}</strong> <small>(option ${{esc(a.option)}})</small>${{facts.length?`<br>${{facts.join('<br>')}}`:''}}`;
  }});
  out+=list('Uncertainties',d.uncertainties); document.getElementById('detail').innerHTML=out;
}}
network.on('click',params=>{{
  schedulePersist();
  if(!params.nodes.length)return;
  const clicked=nodes.get(params.nodes[0]);
  if(clicked?.group==='graph_expander'){{setGraphIncluded(clicked.expandGraph,true);return;}}
  showDetail(params.nodes[0]);
}});
network.on('zoom',schedulePersist);
network.on('dragEnd',schedulePersist);
network.on('animationFinished',schedulePersist);
network.on('selectNode',schedulePersist);
network.on('selectEdge',schedulePersist);
network.on('deselectNode',schedulePersist);
network.on('deselectEdge',schedulePersist);
window.addEventListener('beforeunload',persistState);
setLoading(80,'Knoten und Kanten werden gezeichnet');
await nextPaint();
applyFilter(validSavedView(savedState.view));
if(savedState.selection&&typeof savedState.selection==='object'){{
  const selectedNodes=Array.isArray(savedState.selection.nodes)?savedState.selection.nodes.filter(id=>nodes.get(id)):[];
  const selectedEdges=Array.isArray(savedState.selection.edges)?savedState.selection.edges.filter(id=>edges.get(id)):[];
  network.setSelection({{nodes:selectedNodes,edges:selectedEdges}},{{unselectAll:true,highlightEdges:false}});
  if(selectedNodes.length===1)showDetail(selectedNodes[0]);
}}
stateReady=true;persistState();
setLoading(100,'Fertig');
await nextPaint();
loadingOverlay.hidden=true;
}}
initializeGraph().catch(error=>{{
  loadingCard.classList.add('error');
  loadingTitle.textContent='Quest graph konnte nicht geladen werden';
  loadingMessage.textContent=error instanceof Error?error.message:String(error);
  console.error(error);
}});
</script></body></html>"""


def write_quest_graph_html(output_dir: Path, analyses: list[GraphAnalysis],
                           phrase_unlocks: dict[str, list[str]] | None = None,
                           game_data_scripts: dict[str, list[dict[str, Any]]] | None = None,
                           node_names: dict[str, str] | None = None) -> str:
    filename = "QUEST_GRAPH.html"
    data = build_quest_graph_data(analyses, phrase_unlocks, game_data_scripts, node_names)
    (output_dir / filename).write_text(render_quest_graph_html(data), encoding="utf-8", newline="\n")
    return filename
