"""Small dependency-free ORT graph-assignment attestation helper."""

MAX_ASSIGNMENT_SUBGRAPHS = 4096
MAX_ASSIGNMENT_NODES = 1_000_000
EXPECTED_GRAPHS = ("encoder", "decoder", "joint")


def collect_graph_assignment_facts(sessions):
    """Count nodes by assigned EP without retaining node names or graph payloads."""
    if not isinstance(sessions, dict) or set(sessions) != set(EXPECTED_GRAPHS):
        raise RuntimeError("incomplete acoustic session set for assignment attestation")
    result = {}
    for graph in EXPECTED_GRAPHS:
        session = sessions[graph]
        get_assignments = getattr(session, "get_provider_graph_assignment_info", None)
        if not callable(get_assignments):
            raise RuntimeError("ORT graph assignment readback is unavailable")
        assignments = get_assignments()
        if not isinstance(assignments, (list, tuple)) or not assignments:
            raise RuntimeError("ORT graph assignment readback is empty")
        if len(assignments) > MAX_ASSIGNMENT_SUBGRAPHS:
            raise RuntimeError("ORT graph assignment subgraph bound exceeded")
        counts = {}
        total = 0
        for subgraph in assignments:
            provider = getattr(subgraph, "ep_name", None)
            get_nodes = getattr(subgraph, "get_nodes", None)
            if (not isinstance(provider, str) or not provider
                    or len(provider) > 80 or not callable(get_nodes)):
                raise RuntimeError("ORT graph assignment record is incomplete")
            nodes = get_nodes()
            try:
                node_count = len(nodes)
            except Exception as exc:
                raise RuntimeError("ORT graph assignment node count is unavailable") from exc
            if (not isinstance(node_count, int) or node_count < 0
                    or node_count > MAX_ASSIGNMENT_NODES
                    or total + node_count > MAX_ASSIGNMENT_NODES):
                raise RuntimeError("ORT graph assignment node bound exceeded")
            counts[provider] = counts.get(provider, 0) + node_count
            total += node_count
        if total <= 0:
            raise RuntimeError("ORT acoustic graph reports no placed nodes")
        result[graph] = {"providers": dict(sorted(counts.items())),
                         "total_nodes": total,
                         "method": "get_provider_graph_assignment_info"}
    return result
