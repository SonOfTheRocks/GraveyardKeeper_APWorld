from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .mapping import APWorldIndex
from .model import GraphAnalysis, display_value
from .parser import unwrap_content
from .summaries import QuestSummary, build_phrase_unlock_index, build_quest_summaries
from .graph_report import write_quest_graph_html


def _summary_matches(summary: QuestSummary, item: str | None, node: str | None,
                     target_type: str | None) -> bool:
    if item and not any(item.casefold() in (drop.item or "").casefold() for drop in summary.item_drops):
        return False
    if node and node not in summary.reward_nodes and node not in summary.reference:
        return False
    if target_type == "item" and not summary.item_drops:
        return False
    if target_type == "relation" and not summary.add_relations:
        return False
    return True


def _list(lines: list[str], name: str, values: list[str]) -> None:
    if not values:
        return
    lines += [f"{name}:", ""]
    lines += [f"- {value}" for value in values]
    lines.append("")


def _render_summary(summary: QuestSummary, apworld: APWorldIndex, details: bool) -> str:
    lines = [f"file: {summary.graph}.json", "", f"reward_count: {summary.reward_count}", ""]
    if summary.relation_rewards or summary.item_drops:
        lines += ["rewards:", ""]
        for reward in summary.relation_rewards:
            lines += ["- type: relation", f"  amount: {display_value(reward.amount)}",
                      f"  npc: {reward.npc or 'unresolved'}"]
            if reward.npc_source:
                lines.append(f"  npc_source: {reward.npc_source}")
        for drop in summary.item_drops:
            lines += ["- type: item_drop", f"  item: {drop.item or 'dynamic/unresolved'}",
                      f"  amount: {display_value(drop.amount)}"]
            if drop.resolution:
                lines.append(f"  resolution: {drop.resolution}")
        lines.append("")
    if summary.multi_answer is not None:
        lines += [f"multi_answer: {summary.multi_answer}", ""]
    _list(lines, "required_quests", summary.required_quests)
    _list(lines, "required_quest_sources", summary.phrase_unlock_sources)
    if summary.required_happiness:
        lines += ["required_happiness:", ""]
        for requirement in summary.required_happiness:
            lines += [f"- amount: {display_value(requirement.amount)}",
                      f"  npc: {requirement.npc or 'unresolved'}"]
            if requirement.npc_source:
                lines.append(f"  npc_source: {requirement.npc_source}")
        lines.append("")
    _list(lines, "required_items", summary.required_items)
    _list(lines, "costs", summary.costs)
    _list(lines, "other_requirements", summary.other_requirements)
    _list(lines, "conversations", summary.conversations)
    if summary.task_states:
        lines += ["task_states:", ""]
        lines += [f"- {entry.task}: {entry.state}" for entry in summary.task_states]
        lines.append("")
    _list(lines, "phrases_to_blacklist", summary.phrases_to_blacklist)
    _list(lines, "phrases_removed_from_blacklist", summary.phrases_removed_from_blacklist)
    _list(lines, "phrases_unlocked", summary.phrases_unlocked)
    suggestions: list[str] = []
    for drop in summary.item_drops:
        _append_unique(suggestions, apworld.suggest(drop.item))
    _list(lines, "apworld_item_suggestions", suggestions)
    if details:
        lines += [f"reference: {summary.reference}", ""]
        if summary.multi_answer_index is not None:
            lines += [f"multi_answer_index: {summary.multi_answer_index}", ""]
        _list(lines, "uncertainties", summary.uncertainties)
        _list(lines, "evidence", summary.evidence)
    return "\n".join(lines).rstrip()


def _append_unique(target: list[Any], values: list[Any]) -> None:
    for value in values:
        if value not in target:
            target.append(value)


def render_graph(analysis: GraphAnalysis, apworld: APWorldIndex, *, item: str | None = None,
                 node: str | None = None, target_type: str | None = None,
                 phrase_unlocks: dict[str, list[str]] | None = None, details: bool = False) -> str:
    phrase_unlocks = phrase_unlocks if phrase_unlocks is not None else build_phrase_unlock_index([analysis])
    summaries = [
        summary for summary in build_quest_summaries(analysis, phrase_unlocks)
        if _summary_matches(summary, item, node, target_type)
    ]
    return "\n\n---\n\n".join(_render_summary(summary, apworld, details) for summary in summaries) + ("\n" if summaries else "")


def render_readme(analyses: list[GraphAnalysis], parse_errors: list[str], filters: dict[str, str | None],
                  phrase_unlocks: dict[str, list[str]] | None = None) -> str:
    phrase_unlocks = phrase_unlocks if phrase_unlocks is not None else build_phrase_unlock_index(analyses)
    by_graph: dict[str, list[QuestSummary]] = {}
    for analysis in analyses:
        summaries = [
            summary for summary in build_quest_summaries(analysis, phrase_unlocks)
            if _summary_matches(summary, filters.get("item"), filters.get("node"), filters.get("target_type"))
        ]
        if summaries:
            by_graph[analysis.graph.name] = summaries
    all_summaries = [summary for summaries in by_graph.values() for summary in summaries]
    lines = ["# FlowGraph-Questzusammenfassungen", "",
             "Kompakte, automatisch erzeugte Daten zur manuellen Übertragung in die APWorld-Questdaten.", "",
             "## Zusammenfassung", "",
             f"- Gelesene Graphen: {len(analyses)}",
             f"- Nicht lesbare Graphen: {len(parse_errors)}",
             f"- Belohnungsoptionen/-pfade: {len(all_summaries)}",
             f"- ItemDrops: {sum(len(summary.item_drops) for summary in all_summaries)}",
             f"- Einflussgewinne: {sum(len(summary.relation_rewards) for summary in all_summaries)}",
             f"- Erkannte required_quests aus Phrases: {sum(len(summary.required_quests) for summary in all_summaries)}",
             "", "## Begleitindizes", "", "- [Node- und Verbindungsinventar](INVENTORY.md)",
             "- [Graphübergreifender Setter-Index](SETTER_INDEX.md)",
             "- [Interaktiver gerichteter Questgraph](QUEST_GRAPH.html)", ""]
    if parse_errors:
        lines += ["## Nicht lesbare Dateien", ""] + [f"- {error}" for error in parse_errors] + [""]
    lines += ["## Berichte", ""]
    for graph_name, summaries in sorted(by_graph.items()):
        lines.append(f"- [{graph_name}]({graph_name}.md): {len(summaries)} Einträge")
    lines += ["", "## Bedeutung", "",
              "- `required_quests` stammen aus allen nichtleeren Phrases einer MultiAnswer-Option; ein führendes `@` wird entfernt.",
              "- `required_quest_sources` nennt gefundene `Flow_UnlockPhrase`-Stellen, Blacklist-Entfernungen oder die belegte anfängliche Sichtbarkeitsregel.",
              "- `reward_count` zählt getrennte ItemDrops und positive Einflussgewinne des Eintrags.",
              "- `rewards` führt ItemDrops und Relationsgewinne gemeinsam auf; NPC-Herkünfte werden kenntlich gemacht.",
              "- Gesprächszeilen stehen belohnungsnah zuerst; Task-State-Änderungen bleiben in Ausführungsreihenfolge.",
              "- Technische Belege und Unsicherheiten werden nur mit `--details` ausgegeben.", ""]
    return "\n".join(lines)


def render_inventory(analyses: list[GraphAnalysis], parse_errors: list[str]) -> str:
    node_types = Counter(node.type_name for analysis in analyses for node in analysis.graph.nodes.values())
    edge_types = Counter((edge.kind, edge.raw_type) for analysis in analyses for edge in analysis.graph.edges)
    unsupported = Counter(node.type_name for analysis in analyses for node in analysis.graph.nodes.values()
                          if node.type_name in analysis.unsupported_types)
    diagnostics = sum(len(analysis.graph.diagnostics) for analysis in analyses)
    duplicates = sum(analysis.graph.duplicate_edges for analysis in analyses)
    lines = ["# FlowGraph-Inventar", "", "## Abdeckung", "",
             f"- Graphen: {len(analyses)}", f"- Nicht lesbare Dateien: {len(parse_errors)}",
             f"- Nodes: {sum(node_types.values())}",
             f"- Verbindungen nach Deduplizierung: {sum(edge_types.values())}",
             f"- Deduplizierte identische Verbindungen: {duplicates}",
             f"- Parserdiagnosen: {diagnostics}", "", "## Node-Typen", "",
             "| Typ | Anzahl | Eigene Semantik |", "|---|---:|:---:|"]
    for type_name, count in sorted(node_types.items(), key=lambda entry: (-entry[1], entry[0])):
        lines.append(f"| `{type_name}` | {count} | {'nein' if type_name in unsupported else 'ja/durchgereicht'} |")
    lines += ["", "## Verbindungstypen", "", "| Art | Serialisierter Typ | Anzahl |", "|---|---|---:|"]
    for (kind, raw_type), count in sorted(edge_types.items(), key=lambda entry: (-entry[1], entry[0])):
        lines.append(f"| {kind} | `{raw_type}` | {count} |")
    lines += ["", "## Nicht unterstützte Node-Typen", ""]
    lines += ([f"- `{name}`: {count}" for name, count in sorted(unsupported.items(), key=lambda entry: (-entry[1], entry[0]))]
              or ["- keine"])
    if parse_errors:
        lines += ["", "## Nicht lesbare Dateien", ""] + [f"- {error}" for error in parse_errors]
    return "\n".join(lines) + "\n"


def _raw_scalar(node, names: tuple[str, ...]):
    for name in names:
        if name in node.inputs:
            value = unwrap_content(node.inputs[name])
            if not isinstance(value, (dict, list)):
                return value
    return None


def render_setter_index(analyses: list[GraphAnalysis]) -> str:
    setters: dict[str, list[str]] = {}
    setter_types = {"Flow_SetTaskState", "Flow_SetPlayerParam", "Flow_AddPlayerParam",
                    "Flow_SetWGOParam", "Flow_AddWGOParam"}
    for analysis in analyses:
        for node in analysis.graph.nodes.values():
            if node.type_name not in setter_types:
                continue
            subject = _raw_scalar(node, ("Task", "Param name", "param"))
            value = _raw_scalar(node, ("State", "Value", "value"))
            owner = _raw_scalar(node, ("NPC id", "npc_id", "WGO"))
            key = f"{node.type_name}: {subject if subject is not None else '?'}"
            detail = f"`{analysis.graph.name}:{node.id}` -> {display_value(value)}"
            if owner is not None:
                detail += f"; owner/NPC `{owner}`"
            setters.setdefault(key, []).append(detail)
    lines = ["# Graphübergreifender Setter-Index", "",
             "> Setter sind Kandidaten für Vorgängerzusammenhänge, kein Beweis für eine eindeutige Questabhängigkeit.", ""]
    for key in sorted(setters, key=str.casefold):
        lines += [f"## {key}", ""] + [f"- {entry}" for entry in sorted(setters[key])] + [""]
    return "\n".join(lines)


def write_reports(output_dir: Path, analyses: list[GraphAnalysis], parse_errors: list[str], apworld: APWorldIndex,
                  filters: dict[str, str | None], *, details: bool = False,
                  phrase_unlocks: dict[str, list[str]] | None = None,
                  game_data_scripts: dict[str, list[dict]] | None = None,
                  node_names: dict[str, str] | None = None) -> set[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    phrase_unlocks = phrase_unlocks if phrase_unlocks is not None else build_phrase_unlock_index(analyses)
    written = {"README.md", "INVENTORY.md", "SETTER_INDEX.md"}
    for analysis in analyses:
        report = render_graph(analysis, apworld, item=filters.get("item"), node=filters.get("node"),
                              target_type=filters.get("target_type"), phrase_unlocks=phrase_unlocks,
                              details=details)
        if report:
            filename = f"{analysis.graph.name}.md"
            (output_dir / filename).write_text(report, encoding="utf-8", newline="\n")
            written.add(filename)
    (output_dir / "README.md").write_text(render_readme(analyses, parse_errors, filters, phrase_unlocks),
                                           encoding="utf-8", newline="\n")
    (output_dir / "INVENTORY.md").write_text(render_inventory(analyses, parse_errors),
                                              encoding="utf-8", newline="\n")
    (output_dir / "SETTER_INDEX.md").write_text(render_setter_index(analyses),
                                                 encoding="utf-8", newline="\n")
    written.add(write_quest_graph_html(
        output_dir, analyses, phrase_unlocks, game_data_scripts, node_names))
    return written
