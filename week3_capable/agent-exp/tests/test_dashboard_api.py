import json
import tempfile
from pathlib import Path
from boukensha.dashboard.app import create_dashboard_app


def _make_app(tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True)
    app = create_dashboard_app(
        config_dir=str(tmp_path),
        sessions_dir=str(sessions_dir),
    )
    app.config["TESTING"] = True
    return app, sessions_dir


def test_index_returns_200(tmp_path):
    app, _ = _make_app(tmp_path)
    with app.test_client() as c:
        r = c.get("/")
        assert r.status_code == 200


def test_api_map_returns_json(tmp_path):
    app, _ = _make_app(tmp_path)
    with app.test_client() as c:
        r = c.get("/api/map")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "nodes" in data
        assert "links" in data


def test_api_players_returns_empty_list_when_none_tracked(tmp_path):
    app, _ = _make_app(tmp_path)
    with app.test_client() as c:
        r = c.get("/api/players")
        assert r.status_code == 200
        assert json.loads(r.data) == []


def test_api_players_returns_tracked_positions(tmp_path):
    from boukensha.memory.player_tracker import PlayerTracker

    tracker = PlayerTracker(tmp_path / "memory")
    tracker.update("Hero", "abc123", "Temple Square")

    app, _ = _make_app(tmp_path)
    with app.test_client() as c:
        r = c.get("/api/players")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data == [
            {
                "name": "Hero",
                "room_hash": "abc123",
                "title": "Temple Square",
                "updated_at": data[0]["updated_at"],
                "prev_room_hash": None,
            }
        ]


def test_api_goal_returns_json(tmp_path):
    app, _ = _make_app(tmp_path)
    with app.test_client() as c:
        r = c.get("/api/goal")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "current_goal" in data


def test_api_sessions_returns_list(tmp_path):
    app, sessions_dir = _make_app(tmp_path)
    # Write a minimal session file
    session_file = sessions_dir / "20260727T000000Z-abc12345.jsonl"
    session_file.write_text(
        json.dumps({"phase": "session_start", "at": "2026-07-27T00:00:00Z", "model": "test", "session_id": "abc12345"}) + "\n"
    )
    with app.test_client() as c:
        r = c.get("/api/sessions")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, list)
        assert len(data) >= 1


def test_api_session_detail_returns_entries(tmp_path):
    app, sessions_dir = _make_app(tmp_path)
    sid = "20260727T000000Z-abc12345"
    session_file = sessions_dir / f"{sid}.jsonl"
    lines = [
        {"phase": "session_start", "at": "2026-07-27T00:00:00Z", "model": "test", "session_id": sid},
        {"phase": "turn", "n": 1, "at": "2026-07-27T00:00:01Z", "session_id": sid},
    ]
    session_file.write_text("\n".join(json.dumps(l) for l in lines) + "\n")
    with app.test_client() as c:
        r = c.get(f"/api/sessions/{sid}")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, list)


def test_api_overview_returns_zero_stats_when_no_data(tmp_path):
    app, _ = _make_app(tmp_path)
    with app.test_client() as c:
        r = c.get("/api/overview")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["rooms_known"] == 0
        assert data["frontier"] == {"known_exits": 0, "walked": 0, "frontier": 0}
        assert data["entities"] == {"mobs": 0, "objects": 0, "total": 0}
        assert data["players"] == []


def test_api_overview_reports_rooms_and_players(tmp_path):
    from boukensha.memory.world_graph import WorldGraph
    from boukensha.memory.room_memory import RoomMemory
    from boukensha.memory.player_tracker import PlayerTracker

    memory_dir = tmp_path / "memory"
    mem = RoomMemory(memory_dir)
    graph = WorldGraph(memory_dir)
    room = {"title": "Main Street", "description": "d", "exits": {"north": "..."}, "npcs": [], "items": []}
    h, _ = mem.record(room)
    graph.add_room(h, "Main Street")
    graph.save()

    tracker = PlayerTracker(memory_dir)
    tracker.update("Hero", h, "Main Street")
    tracker.update_stats("Hero", {"hp": 20, "max_hp": 20, "mana": 100, "max_mana": 100, "move": 85, "max_move": 85})

    app, _ = _make_app(tmp_path)
    with app.test_client() as c:
        r = c.get("/api/overview")
        data = json.loads(r.data)
        assert data["rooms_known"] == 1
        assert data["frontier"] == {"known_exits": 1, "walked": 0, "frontier": 1}
        assert data["players"][0]["name"] == "Hero"
        assert data["players"][0]["stats"]["hp"] == 20


def test_index_includes_overview_tab(tmp_path):
    app, _ = _make_app(tmp_path)
    with app.test_client() as c:
        r = c.get("/")
        html = r.data.decode()
        assert 'data-tab="overview"' in html
        assert 'id="tab-overview"' in html


def test_api_map_includes_enrichment_fields(tmp_path):
    from boukensha.memory.world_graph import WorldGraph
    from boukensha.memory.room_memory import RoomMemory

    memory_dir = tmp_path / "memory"
    graph = WorldGraph(memory_dir)
    mem = RoomMemory(memory_dir)

    room_a = {"title": "Temple Square", "description": "d", "exits": {"north": "x"}, "npcs": ["a guard"], "items": []}
    hash_a, _ = mem.record(room_a)
    graph.add_room(hash_a, "Temple Square")

    room_b = {"title": "Wall Road", "description": "d", "exits": {}, "npcs": [], "items": []}
    hash_b, _ = mem.record(room_b)
    graph.add_room(hash_b, "Wall Road")

    # to_room_exits omitted so the south reverse edge is auto-filled as
    # "inferred" (see the note in test_map_enrichment.py's equivalent case).
    graph.add_edge(hash_a, hash_b, "north")
    graph.save()

    app, _ = _make_app(tmp_path)
    with app.test_client() as c:
        r = c.get("/api/map")
        assert r.status_code == 200
        data = json.loads(r.data)

    node_a = next(n for n in data["nodes"] if n["id"] == hash_a)
    assert node_a["npc_count"] == 1
    assert node_a["item_count"] == 0
    assert "zone_id" in node_a
    assert "zone_label" in node_a
    assert node_a["aliases"] == []

    link = next(l for l in data["links"] if l["source"] == hash_a and l["target"] == hash_b)
    assert link["kind"] == "walked"
    reverse = next(l for l in data["links"] if l["source"] == hash_b and l["target"] == hash_a)
    assert reverse["kind"] == "inferred"
