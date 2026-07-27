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
