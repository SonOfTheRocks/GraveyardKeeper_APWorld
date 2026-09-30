from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .analysis import AnalysisLimits, _inventory_requirement
from .model import DialogueOption, Graph, GraphAnalysis, RewardFinding, SymbolicValue, display_value
from .parser import unwrap_content
from .values import ValueResolver


def _literal(raw: Any) -> Any:
    value = unwrap_content(raw)
    return value if not isinstance(value, (dict, list)) else None


def _input(node: Any, *names: str) -> Any:
    for name in names:
        if name in node.inputs:
            value = _literal(node.inputs[name])
            if value is not None:
                return value
    return None


def _without_at(value: str) -> str:
    return value[1:] if value.startswith("@") else value


def _append_unique(target: list[Any], values: Iterable[Any]) -> None:
    for value in values:
        if value not in target:
            target.append(value)


@dataclass(frozen=True)
class ItemDropSummary:
    item: str | None
    amount: Any
    resolution: str | None = None


@dataclass(frozen=True)
class RelationRewardSummary:
    amount: Any
    npc: str | None
    npc_source: str | None


@dataclass(frozen=True)
class HappinessRequirement:
    amount: Any
    npc: str | None
    npc_source: str | None


@dataclass(frozen=True)
class TaskStateSummary:
    task: str
    state: str


@dataclass
class QuestSummary:
    graph: str
    reference: str
    multi_answer: str | None = None
    multi_answer_node: str | None = None
    multi_answer_index: int | None = None
    relation_rewards: list[RelationRewardSummary] = field(default_factory=list)
    item_drops: list[ItemDropSummary] = field(default_factory=list)
    conversations: list[str] = field(default_factory=list)
    task_states: list[TaskStateSummary] = field(default_factory=list)
    phrases_to_blacklist: list[str] = field(default_factory=list)
    phrases_removed_from_blacklist: list[str] = field(default_factory=list)
    required_quests: list[str] = field(default_factory=list)
    phrase_unlock_sources: list[str] = field(default_factory=list)
    required_happiness: list[HappinessRequirement] = field(default_factory=list)
    required_items: list[str] = field(default_factory=list)
    costs: list[str] = field(default_factory=list)
    other_requirements: list[str] = field(default_factory=list)
    function_calls: list[str] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    reward_nodes: set[str] = field(default_factory=set)
    node_ids: set[str] = field(default_factory=set)
    flow_steps: set[tuple[str, str, str]] = field(default_factory=set)
    phrases_unlocked: list[str] = field(default_factory=list)

    @property
    def add_relations(self) -> list[Any]:
        return [reward.amount for reward in self.relation_rewards]

    @property
    def reward_count(self) -> int:
        return len(self.relation_rewards) + len(self.item_drops)


def _graph_npc(graph: str) -> tuple[str | None, str | None]:
    if graph.startswith("npc_"):
        return graph[4:].replace(" ", "_"), "aus Graph-Dateiname abgeleitet"
    return None, None


def build_phrase_unlock_index(analyses: Iterable[GraphAnalysis]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for analysis in analyses:
        for node in analysis.graph.nodes.values():
            is_unlock = node.type_name == "Flow_UnlockPhrase"
            is_blacklist_removal = (
                node.type_name == "Flow_AddPhraseToBlacklist"
                and bool(_input(node, "remove"))
            )
            if not is_unlock and not is_blacklist_removal:
                continue
            phrase = _input(node, "Phrase", "Phrase ID")
            if not isinstance(phrase, str) or not phrase:
                continue
            index.setdefault(_without_at(phrase), []).append(f"{analysis.graph.name}.json:{node.id}")
    for sources in index.values():
        sources.sort()
    return index


def _option_paths(graph: Graph, option: DialogueOption, limits: AnalysisLimits) -> tuple[list[list[str]], list[str]]:
    completed: list[list[str]] = []
    issues: list[str] = []
    states = 0
    # A frame retains the call node and its ordinary continuation edges. FlowCanvas
    # serializes the jump to CustomFunctionEvent by UID, while Return resumes those
    # continuation edges; treating Return as an unconditional endpoint loses the
    # remainder of long quest/cutscene chains.
    call_stack_type = tuple[tuple[str, tuple[Any, ...]], ...]
    stack: list[tuple[str, list[str], call_stack_type, frozenset[tuple[str, tuple[str, ...]]]]] = []
    for target in reversed(option.target_nodes):
        initial_key = (target, ())
        stack.append((target, [option.multi_answer_node, target], (), frozenset({initial_key})))
    while stack:
        current, path, call_stack, visited = stack.pop()
        states += 1
        if states > limits.max_states:
            issues.append(f"state limit {limits.max_states} reached")
            break
        if len(path) > limits.max_depth:
            issues.append(f"depth limit {limits.max_depth} reached")
            continue
        node = graph.nodes[current]
        if node.type_name == "Return":
            if not call_stack:
                completed.append(path)
                continue
            _, outgoing = call_stack[-1]
            next_call_stack = call_stack[:-1]
        else:
            outgoing = tuple(graph.outgoing_flow[current])
            next_call_stack = call_stack
        if node.type_name == "CustomFunctionCall":
            call_edges = [edge for edge in outgoing if edge.raw_type == "Synthetic.CustomFunctionCall"]
            if call_edges:
                continuations = tuple(
                    edge for edge in graph.outgoing_flow[current]
                    if edge.raw_type != "Synthetic.CustomFunctionCall"
                )
                next_call_stack = call_stack + ((node.id, continuations),)
                outgoing = tuple(call_edges)
        elif node.type_name == "Flow_MultiAnswer":
            # A nested menu begins a new user choice and must not be folded into this option.
            completed.append(path)
            continue
        if not outgoing:
            completed.append(path)
            continue
        progressed = False
        for edge in reversed(outgoing):
            stack_signature = tuple(frame[0] for frame in next_call_stack)
            state_key = (edge.target, stack_signature)
            if state_key in visited:
                issues.append(f"loop through node {edge.target} skipped")
                continue
            progressed = True
            stack.append((
                edge.target, path + [edge.target], next_call_stack,
                visited | {state_key},
            ))
        if not progressed:
            completed.append(path)
        if len(completed) >= limits.max_paths:
            issues.append(f"path limit {limits.max_paths} reached")
            break
    unique: dict[tuple[str, ...], list[str]] = {}
    for path in completed:
        unique.setdefault(tuple(path), path)
    return list(unique.values()), sorted(set(issues))


def _reward_map(analysis: GraphAnalysis) -> dict[str, list[RewardFinding]]:
    result: dict[str, list[RewardFinding]] = {}
    for finding in analysis.findings:
        if finding.option is None:
            result.setdefault(finding.node_id, []).append(finding)
    return result


def _add_reward(summary: QuestSummary, finding: RewardFinding) -> None:
    if finding.node_id in summary.reward_nodes:
        return
    summary.reward_nodes.add(finding.node_id)
    if finding.kind == "relation":
        npc, source = ((finding.npc_id, "explizites npc_id-Feld") if finding.npc_id else _graph_npc(summary.graph))
        summary.relation_rewards.append(RelationRewardSummary(finding.amount, npc, source))
    else:
        reward = ItemDropSummary(finding.resource_id, finding.amount, finding.resource_detail)
        summary.item_drops.append(reward)
    _append_unique(summary.uncertainties, finding.issues)


def _usable_smart_res(value: SymbolicValue | None) -> bool:
    return bool(
        value
        and value.kind == "smart_res"
        and value.resource_type
        and value.resource_id
        and value.amount is not None
        and not isinstance(value.amount, (dict, list))
    )


def _add_answer_data(summary: QuestSummary, option: DialogueOption) -> None:
    answer = option.answer
    if answer is None:
        return
    if _usable_smart_res(answer.lock):
        lock = answer.lock
        if lock.resource_type == "GameRes" and lock.resource_id == "_rel":
            npc, source = _graph_npc(summary.graph)
            _append_unique(summary.required_happiness, [HappinessRequirement(lock.amount, npc, source)])
        elif lock.resource_type == "Item":
            _append_unique(summary.required_items, [f"{lock.resource_id or '?'} x{display_value(lock.amount)}"])
        else:
            _append_unique(summary.other_requirements, [f"answer lock: {lock.render()}"])
    if _usable_smart_res(answer.price):
        if answer.price.resource_type == "Item":
            _append_unique(summary.required_items, [
                f"{answer.price.resource_id or 'dynamic/unresolved'} x{display_value(answer.price.amount)}"
            ])
        else:
            _append_unique(summary.costs, [answer.price.render()])
    reward = answer.reward
    if _usable_smart_res(reward):
        if reward.resource_type == "GameRes" and reward.resource_id == "_rel":
            npc, source = _graph_npc(summary.graph)
            summary.relation_rewards.append(RelationRewardSummary(reward.amount, npc, source))
            _append_unique(summary.uncertainties, ["Empfänger des AnswerData-Relationsgewinns ist implizit"])
        elif reward.resource_type == "Item":
            item = ItemDropSummary(reward.resource_id, reward.amount)
            summary.item_drops.append(item)


def _answer_price_requirements(option: DialogueOption) -> tuple[set[str], set[str]]:
    """Return the item/currency requirements imposed by one AnswerData.price."""
    answer = option.answer
    if answer is None or not _usable_smart_res(answer.price):
        return set(), set()
    if answer.price.resource_type == "Item":
        return {
            f"{answer.price.resource_id or 'dynamic/unresolved'} "
            f"x{display_value(answer.price.amount)}"
        }, set()
    return set(), {answer.price.render()}


def _add_nodes(summary: QuestSummary, graph: Graph, node_ids: list[str], reward_map: dict[str, list[RewardFinding]]) -> None:
    summary.node_ids.update(node_ids)
    for source, target in zip(node_ids, node_ids[1:]):
        for edge in graph.outgoing_flow[source]:
            if edge.target == target:
                summary.flow_steps.add((source, edge.source_port, target))
    talks_in_execution_order: list[str] = []
    for node_id in node_ids:
        node = graph.nodes[node_id]
        if node.type_name == "Flow_Talk":
            text = _input(node, "Text")
            if isinstance(text, str) and text:
                talks_in_execution_order.append(text)
        elif node.type_name == "Flow_SetTaskState":
            task = _input(node, "Task")
            state = _input(node, "State")
            if task is not None and state is not None:
                item = TaskStateSummary(str(task), str(state))
                if item not in summary.task_states:
                    summary.task_states.append(item)
        elif node.type_name == "Flow_AddPhraseToBlacklist":
            phrase = _input(node, "Phrase ID", "Phrase")
            remove = bool(_input(node, "remove"))
            if isinstance(phrase, str) and phrase:
                target = summary.phrases_removed_from_blacklist if remove else summary.phrases_to_blacklist
                _append_unique(target, [_without_at(phrase)])
        elif node.type_name == "Flow_UnlockPhrase":
            phrase = _input(node, "Phrase ID", "Phrase")
            if isinstance(phrase, str) and phrase:
                _append_unique(summary.phrases_unlocked, [_without_at(phrase)])
        elif node.type_name == "Flow_RemoveItemFromInventory":
            item = _input(node, "Item ID", "Res_id")
            amount = _input(node, "Items Count", "Amount")
            _append_unique(summary.required_items, [
                f"{item or 'dynamic/unresolved'} x{display_value(amount if amount is not None else 1)}"
            ])
        elif node.type_name == "CustomFunctionCall":
            call_edges = [
                edge for edge in graph.outgoing_flow[node.id]
                if edge.raw_type == "Synthetic.CustomFunctionCall"
            ]
            for edge in call_edges:
                event = graph.nodes[edge.target]
                identifier = event.raw.get("identifier") or _input(event, "Event")
                label = str(identifier) if identifier else event.type_name
                _append_unique(summary.function_calls, [
                    f"{node.id} -> {label} (CustomFunctionEvent {event.id})"
                ])
        elif node.type_name == "Flow_RunScript":
            script = _input(node, "Script name")
            if isinstance(script, str) and script:
                _append_unique(summary.function_calls, [
                    f"{node.id} -> {script} (Flow_RunScript)"
                ])
        for finding in reward_map.get(node_id, []):
            _add_reward(summary, finding)
    _append_unique(summary.conversations, reversed(talks_in_execution_order))


def _inventory_requirements_for_path(graph: Graph, resolver: ValueResolver,
                                     node_ids: list[str]) -> set[str]:
    requirements: set[str] = set()
    for source, target in zip(node_ids, node_ids[1:]):
        node = graph.nodes[source]
        if node.type_name != "Flow_HasItemInInventory":
            continue
        matching_ports = {
            edge.source_port.strip().casefold()
            for edge in graph.outgoing_flow[source] if edge.target == target
        }
        if "yes" in matching_ports and "no" not in matching_ports:
            item_id, amount = _inventory_requirement(resolver, source)
            requirements.add(f"{item_id or 'dynamic/unresolved'} x{display_value(amount)}")
    return requirements


def _add_common_inventory_requirements(summary: QuestSummary,
                                       requirements_by_path: list[set[str]]) -> None:
    if not requirements_by_path:
        return
    common = set.intersection(*requirements_by_path)
    _append_unique(summary.required_items, sorted(common))


def build_quest_summaries(analysis: GraphAnalysis, phrase_unlocks: dict[str, list[str]],
                          limits: AnalysisLimits | None = None, *,
                          include_without_rewards: bool = False) -> list[QuestSummary]:
    limits = limits or AnalysisLimits()
    rewards = _reward_map(analysis)
    resolver = ValueResolver(analysis.graph)
    summaries: list[QuestSummary] = []
    consumed_reward_nodes: set[str] = set()

    option_path_data: dict[tuple[str, int], tuple[list[list[str]], list[str]]] = {}
    nested_menu_prices: dict[str, dict[tuple[str, int], tuple[set[str], set[str]]]] = {}
    for option in analysis.options:
        option_key = option.multi_answer_node, option.index
        paths_and_issues = _option_paths(analysis.graph, option, limits)
        option_path_data[option_key] = paths_and_issues
        price_requirements = _answer_price_requirements(option)
        for path in paths_and_issues[0]:
            target = path[-1]
            if (target != option.multi_answer_node
                    and analysis.graph.nodes[target].type_name == "Flow_MultiAnswer"):
                nested_menu_prices.setdefault(target, {})[option_key] = price_requirements

    inherited_menu_prices: dict[str, tuple[set[str], set[str]]] = {}
    for menu_id, entries in nested_menu_prices.items():
        requirements = list(entries.values())
        inherited_menu_prices[menu_id] = (
            set.intersection(*(items for items, _ in requirements)),
            set.intersection(*(costs for _, costs in requirements)),
        )

    for option in analysis.options:
        paths, path_issues = option_path_data[(option.multi_answer_node, option.index)]
        summary = QuestSummary(
            graph=analysis.graph.name,
            reference=f"{analysis.graph.name}:{option.multi_answer_node}:option:{option.index}",
            multi_answer=option.phrase,
            multi_answer_node=option.multi_answer_node,
            multi_answer_index=option.index,
        )
        if isinstance(option.phrase, str) and option.phrase:
            phrase = _without_at(option.phrase)
            summary.required_quests.append(phrase)
            _append_unique(summary.phrase_unlock_sources, phrase_unlocks.get(phrase, []))
            if phrase not in phrase_unlocks:
                if option.phrase.startswith("@"):
                    summary.uncertainties.append(
                        f"Keine Phrase-Freischaltquelle für {phrase} gefunden")
                else:
                    # MultiAnswerGUI only checks unlocked_phrases for answer IDs
                    # beginning with '@'. Plain IDs therefore need no stored
                    # unlock, but remain quest-relevant because blacklist state
                    # can still hide them.
                    summary.phrase_unlock_sources.append(
                        "Beim neuen Spiel sichtbar (MultiAnswerGUI-Regel: kein @-Präfix)"
                    )
        inherited_items, inherited_costs = inherited_menu_prices.get(
            option.multi_answer_node, (set(), set()))
        _append_unique(summary.required_items, sorted(inherited_items))
        _append_unique(summary.costs, sorted(inherited_costs))
        _add_answer_data(summary, option)
        _append_unique(summary.uncertainties, option.issues)
        _append_unique(summary.uncertainties, path_issues)
        inventory_requirements: list[set[str]] = []
        for path in paths:
            _add_nodes(summary, analysis.graph, path[1:], rewards)
            inventory_requirements.append(
                _inventory_requirements_for_path(analysis.graph, resolver, path))
            summary.evidence.append(" -> ".join(path))
        _add_common_inventory_requirements(summary, inventory_requirements)
        has_script_call = any(
            analysis.graph.nodes[node_id].type_name == "Flow_RunScript"
            for node_id in summary.node_ids
        )
        has_event_transition = any(
            analysis.graph.nodes[node_id].type_name in {
                "Flow_FireEvent", "Flow_AddInteractionEvent",
            } or (
                analysis.graph.nodes[node_id].type_name == "Flow_GoTo"
                and isinstance(_input(analysis.graph.nodes[node_id], "finished_event"), str)
                and bool(_input(analysis.graph.nodes[node_id], "finished_event"))
            )
            for node_id in summary.node_ids
        )
        if summary.reward_count or (include_without_rewards and (
                summary.phrases_unlocked or summary.phrases_to_blacklist or
                summary.phrases_removed_from_blacklist or has_script_call or
                has_event_transition)):
            consumed_reward_nodes.update(summary.reward_nodes)
            summaries.append(summary)

    # Rewards outside a selectable conversation remain visible as compact standalone records.
    for finding in analysis.findings:
        if finding.option is not None or finding.node_id in consumed_reward_nodes:
            continue
        summary = QuestSummary(analysis.graph.name, finding.reference)
        _add_reward(summary, finding)
        inventory_requirements = []
        for path in finding.paths:
            _add_nodes(summary, analysis.graph, path.node_ids, {})
            inventory_requirements.append(
                _inventory_requirements_for_path(analysis.graph, resolver, path.node_ids))
            for condition in path.conditions:
                node = analysis.graph.nodes[condition.source.node_id]
                if node.type_name not in {"Flow_HasItemInInventory", "Flow_RemoveItemFromInventory"}:
                    _append_unique(summary.other_requirements, [condition.text])
            _append_unique(summary.costs, [
                cost for cost in path.costs if not cost.startswith("Item ")
            ])
            _append_unique(summary.uncertainties, path.incomplete_reasons)
            summary.evidence.append(" -> ".join(path.node_ids))
        _add_common_inventory_requirements(summary, inventory_requirements)
        summaries.append(summary)

    summaries.sort(key=lambda entry: (
        entry.multi_answer is None,
        (entry.multi_answer or "").casefold(),
        entry.multi_answer_index if entry.multi_answer_index is not None else -1,
        entry.reference,
    ))
    return summaries
