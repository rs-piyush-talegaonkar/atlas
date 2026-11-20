"""Structural tests for the code_agent workflow graph.

These assert the design decisions rather than the behaviour: no model is
called and no network is touched. They exist because the guarantees this
agent makes are structural - the reporter cannot cite a file it never fetched
because it holds no tools - and a guarantee worth making is worth asserting.
"""

from __future__ import annotations

from atlas.agents.code_agent import agent as mod

SCOUTS = ("structure_scout", "dependency_scout", "code_scout")


def nodes_by_name(graph) -> dict:
    if isinstance(graph.nodes, dict):
        return graph.nodes
    return {n.name: n for n in graph.nodes}


def tool_names(llm_agent) -> set[str]:
    return {getattr(t, "__name__", getattr(t, "name", str(t))) for t in llm_agent.tools}


def test_graph_fans_out_to_every_scout_and_joins_before_the_reporter():
    edges = {(e.from_node.name, e.to_node.name) for e in mod.root_agent.graph.edges}
    for scout in SCOUTS:
        assert ("__START__", scout) in edges
        assert (scout, "gather") in edges
    assert ("gather", "reporter") in edges


def test_gather_is_the_only_barrier():
    nodes = nodes_by_name(mod.root_agent.graph)
    assert nodes["gather"]._requires_all_predecessors is True
    for name in (*SCOUTS, "reporter"):
        assert nodes[name]._requires_all_predecessors is False


def test_retry_sits_on_the_nodes_not_the_workflow():
    # A Workflow-level retry restarts the whole graph, so one scout's 429
    # would re-run all three. See the comment on NODE_RETRY.
    assert mod.root_agent.retry_config is None
    for name in (*SCOUTS, "reporter"):
        assert getattr(mod, name).retry_config is not None


def test_retry_covers_both_throttling_and_saturation():
    exceptions = set(mod.NODE_RETRY.exceptions)
    assert "ServerError" in exceptions  # 503
    assert "_ResourceExhaustedError" in exceptions  # 429


def test_retry_delay_ceiling_clears_a_rate_limit_window():
    # A 429 asks for a retry up to about 58 seconds out.
    assert mod.NODE_RETRY.max_delay >= 60.0


def test_the_reporter_holds_no_tools():
    assert not mod.reporter.tools


def test_each_scout_holds_only_the_tools_its_brief_needs():
    assert tool_names(mod.structure_scout) == {"list_repo_files"}
    assert tool_names(mod.dependency_scout) == {"list_repo_files", "read_repo_file"}
    assert tool_names(mod.code_scout) == {"search_repo_code", "read_repo_file"}


def test_no_scout_can_search_and_list_at_once():
    # Overlapping remits make the scouts duplicate each other's work.
    for name in SCOUTS:
        tools = tool_names(getattr(mod, name))
        assert not {"list_repo_files", "search_repo_code"} <= tools


def test_every_scout_carries_the_loop_guard():
    for name in SCOUTS:
        assert "Never repeat a tool call" in getattr(mod, name).instruction


def test_reporter_reads_every_scout_output_key():
    for key in ("structure", "dependencies", "code"):
        assert "{" + key + "}" in mod.reporter.instruction


def test_each_scout_writes_the_key_the_reporter_reads():
    assert mod.structure_scout.output_key == "structure"
    assert mod.dependency_scout.output_key == "dependencies"
    assert mod.code_scout.output_key == "code"
