"""BOM-scoped logical dependency graph reader and propagation traversal.

Edges are scoped by ``product_id`` and use BOM-local ``component_id`` or
logical-node identifiers. A net, rail, or control relationship belongs to a
specific board, so MPN/component-model edges would incorrectly propagate a
relationship from one product to another that happens to use the same part.
The graph is therefore populated only from schematic or netlist evidence.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

from src.industry_data.csv_store import read_csv


DEPENDENCY_GRAPH_FILE = "dependency_graph.csv"
RELATIONSHIP_TYPES = frozenset({"POWERS", "FEEDS_SIGNAL", "SHARES_RAIL", "CONTROLS"})
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
_UNRESOLVED_NODES = {"", "UNKNOWN", "UNRESOLVED", INSUFFICIENT_DATA}


@dataclass(frozen=True)
class DependencyEdge:
    edge_id: str
    product_id: str
    source_node: str
    target_node: str
    relationship_type: str
    function: str
    confidence: str
    source: str

    @classmethod
    def from_row(cls, row: Mapping[str, str]) -> "DependencyEdge":
        relationship_type = str(row.get("relationship_type") or "").strip().upper()
        if relationship_type not in RELATIONSHIP_TYPES:
            raise ValueError(f"Unsupported dependency relationship_type: {relationship_type or '<blank>'}.")
        product_id = str(row.get("product_id") or "").strip()
        if not product_id:
            raise ValueError("Dependency graph edge is missing required product_id.")
        edge_id = str(row.get("edge_id") or "").strip()
        if not edge_id:
            raise ValueError("Dependency graph edge is missing edge_id.")
        source_node = str(row.get("source_node") or "").strip()
        if not source_node:
            raise ValueError("Dependency graph edge is missing source_node.")
        return cls(
            edge_id=edge_id,
            product_id=product_id,
            source_node=source_node,
            target_node=str(row.get("target_node") or "").strip(),
            relationship_type=relationship_type,
            function=str(row.get("function") or "").strip(),
            confidence=str(row.get("confidence") or "").strip() or INSUFFICIENT_DATA,
            source=str(row.get("source") or "").strip() or INSUFFICIENT_DATA,
        )


@dataclass(frozen=True)
class DependencyGraph:
    product_id: str
    adjacency: Dict[str, Tuple[DependencyEdge, ...]]


def _rows(rows: Optional[Iterable[Mapping[str, str]]]) -> Iterable[Mapping[str, str]]:
    return read_csv(DEPENDENCY_GRAPH_FILE) if rows is None else rows


def scopes_for_component(component_id: str, rows: Optional[Iterable[Mapping[str, str]]] = None) -> List[str]:
    """Return graph scopes containing a component as either end of an edge."""
    node = str(component_id or "").strip()
    if not node:
        return []
    scopes = {
        str(row.get("product_id") or "").strip()
        for row in _rows(rows)
        if node in {str(row.get("source_node") or "").strip(), str(row.get("target_node") or "").strip()}
        and str(row.get("product_id") or "").strip()
    }
    return sorted(scopes)


def load_component_graph(
    product_id: str,
    component_id: str,
    rows: Optional[Iterable[Mapping[str, str]]] = None,
) -> DependencyGraph:
    """Load directed adjacency for one BOM-scoped component graph.

    The returned graph contains the component's whole product scope so traversal
    can retain intermediate logical nodes such as a voltage rail.
    """
    edges = [DependencyEdge.from_row(row) for row in _rows(rows) if str(row.get("product_id") or "").strip() == product_id]
    node = str(component_id or "").strip()
    if node and not any(node in {edge.source_node, edge.target_node} for edge in edges):
        edges = []
    adjacency: Dict[str, List[DependencyEdge]] = {}
    for edge in edges:
        adjacency.setdefault(edge.source_node, []).append(edge)
    return DependencyGraph(
        product_id=product_id,
        adjacency={node: tuple(node_edges) for node, node_edges in adjacency.items()},
    )


def _node_id(value: str) -> str:
    return value if value.strip().upper() not in _UNRESOLVED_NODES else INSUFFICIENT_DATA


def traverse_downstream(graph: DependencyGraph, changed_node: str) -> List[Dict[str, object]]:
    """Breadth-first directed propagation with explicit paths and evidence fields."""
    start = str(changed_node or "").strip()
    if not start:
        return []
    queue = deque([(start, [start], [])])
    visited = {start}
    affected: List[Dict[str, object]] = []

    while queue:
        node, path, path_edges = queue.popleft()
        for edge in graph.adjacency.get(node, ()):
            target = _node_id(edge.target_node)
            edge_data = {
                "edge_id": edge.edge_id,
                "relationship_type": edge.relationship_type,
                "function": edge.function or INSUFFICIENT_DATA,
                "confidence": edge.confidence,
                "source": edge.source,
            }
            next_path = path + [target]
            next_edges = path_edges + [edge_data]
            resolved = target != INSUFFICIENT_DATA
            affected.append(
                {
                    "node_id": target,
                    "status": "FOUND" if resolved else INSUFFICIENT_DATA,
                    "path": next_path,
                    "path_edges": next_edges,
                    "confidence": edge.confidence if resolved else INSUFFICIENT_DATA,
                    "source": edge.source,
                    "limitations": [] if resolved else ["A graph edge terminates at an unresolved logical node."],
                }
            )
            if resolved and target not in visited:
                visited.add(target)
                queue.append((target, next_path, next_edges))
    return affected
