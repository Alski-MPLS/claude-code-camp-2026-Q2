from boukensha.memory.world_graph import WorldGraph
from boukensha.memory.pathfinder import Pathfinder


def _build_graph(tmp_path):
    g = WorldGraph(tmp_path)
    # A -> B (north), B -> C (east), A -> C (east, longer path)
    g.add_room("aaa", "Room A")
    g.add_room("bbb", "Room B")
    g.add_room("ccc", "Room C")
    g.add_edge("aaa", "bbb", "north")
    g.add_edge("bbb", "ccc", "east")
    g.add_edge("aaa", "ccc", "east")
    return g


def test_find_path_direct(tmp_path):
    g = _build_graph(tmp_path)
    p = Pathfinder(g)
    path = p.find_path("aaa", "bbb")
    assert path == ["north"]


def test_find_path_multi_step(tmp_path):
    g = _build_graph(tmp_path)
    p = Pathfinder(g)
    path = p.find_path("aaa", "ccc")
    # Shortest is direct east (1 step), not north+east (2 steps)
    assert path == ["east"]


def test_find_path_no_route_returns_none(tmp_path):
    g = WorldGraph(tmp_path)
    g.add_room("aaa", "Room A")
    g.add_room("bbb", "Room B")
    p = Pathfinder(g)
    assert p.find_path("aaa", "bbb") is None


def test_find_path_same_room_returns_empty(tmp_path):
    g = _build_graph(tmp_path)
    p = Pathfinder(g)
    path = p.find_path("aaa", "aaa")
    assert path == []


def test_find_path_unknown_start_returns_none(tmp_path):
    g = _build_graph(tmp_path)
    p = Pathfinder(g)
    assert p.find_path("zzz", "bbb") is None


def test_find_path_by_title(tmp_path):
    g = _build_graph(tmp_path)
    p = Pathfinder(g)
    path = p.find_path_by_title("aaa", "Room B")
    assert path == ["north"]


def test_find_path_by_title_no_match_returns_none(tmp_path):
    g = _build_graph(tmp_path)
    p = Pathfinder(g)
    assert p.find_path_by_title("aaa", "Nonexistent") is None


def test_route_to_includes_expected_node_sequence(tmp_path):
    g = _build_graph(tmp_path)
    p = Pathfinder(g)
    route = p.route_to("aaa", "ccc")
    assert route.directions == ["east"]
    assert route.nodes == ["aaa", "ccc"]


def test_route_to_same_room_has_empty_directions_and_single_node(tmp_path):
    g = _build_graph(tmp_path)
    p = Pathfinder(g)
    route = p.route_to("aaa", "aaa")
    assert route.directions == []
    assert route.nodes == ["aaa"]


def test_route_to_no_route_returns_none(tmp_path):
    g = WorldGraph(tmp_path)
    g.add_room("aaa", "Room A")
    g.add_room("bbb", "Room B")
    p = Pathfinder(g)
    assert p.route_to("aaa", "bbb") is None
