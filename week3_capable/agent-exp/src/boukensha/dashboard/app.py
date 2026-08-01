"""Flask dashboard — six tabs with SSE live feed."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, render_template, stream_with_context

from .event_bus import EventBus

_bus: EventBus = EventBus()


def get_bus() -> EventBus:
    return _bus


def create_dashboard_app(
    *,
    config_dir: str,
    sessions_dir: str,
    memory_subdir: str = "memory",
) -> Flask:
    config_path = Path(config_dir)
    sessions_path = Path(sessions_dir)
    memory_path = config_path / memory_subdir

    template_folder = str(Path(__file__).parent / "templates")
    static_folder = str(Path(__file__).parent / "static")
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/events")
    def sse_events():
        def generate():
            yield from _bus.stream()
        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @app.route("/api/map")
    def api_map():
        from boukensha.memory.world_graph import WorldGraph
        from boukensha.memory.room_memory import RoomMemory
        from boukensha.memory.room_aliases import RoomAliases
        from boukensha.memory.map_enrichment import (
            classify_edges, node_frontier, node_aliases, assign_zones,
        )

        g = WorldGraph(memory_path)
        g.load()
        nx_g = g.graph
        mem = RoomMemory(memory_path)
        aliases = RoomAliases(memory_path)

        frontier = node_frontier(g, mem)
        alias_map = node_aliases(aliases)
        zones = assign_zones(g)
        edge_kinds = classify_edges(g, mem)

        nodes = []
        for n, attrs in nx_g.nodes(data=True):
            room = mem.get(n) or {}
            zone = zones.get(n, {"zone_id": 0, "zone_label": "Zone 0", "zone_color": "#3a5f8a"})
            nodes.append({
                "id": n,
                "title": attrs.get("title", n),
                "zone_id": zone["zone_id"],
                "zone_label": zone["zone_label"],
                "zone_color": zone["zone_color"],
                "unwalked": frontier.get(n, 0),
                "aliases": alias_map.get(n, []),
                "npc_count": len(room.get("npcs") or []),
                "item_count": len(room.get("items") or []),
            })
        links = [
            {
                "source": u, "target": v,
                "direction": d.get("direction", ""),
                "kind": edge_kinds.get((u, v), "walked"),
            }
            for u, v, d in nx_g.edges(data=True)
        ]
        return jsonify({"nodes": nodes, "links": links})

    @app.route("/api/players")
    def api_players():
        from boukensha.memory.player_tracker import PlayerTracker
        tracker = PlayerTracker(memory_path)
        players = [
            {"name": name, **info}
            for name, info in tracker.read_all().items()
        ]
        return jsonify(players)

    @app.route("/api/overview")
    def api_overview():
        from boukensha.memory.world_graph import WorldGraph
        from boukensha.memory.room_memory import RoomMemory
        from boukensha.memory.world_stats import frontier_stats, entity_stats
        from boukensha.memory.player_tracker import PlayerTracker

        g = WorldGraph(memory_path)
        g.load()
        mem = RoomMemory(memory_path)
        players = [
            {"name": name, **info}
            for name, info in PlayerTracker(memory_path).read_all().items()
        ]
        return jsonify({
            "rooms_known": g.graph.number_of_nodes(),
            "frontier": frontier_stats(g, mem),
            "entities": entity_stats(g, mem),
            "players": players,
        })

    @app.route("/api/room/<room_hash>")
    def api_room(room_hash: str):
        from boukensha.memory.room_memory import RoomMemory
        mem = RoomMemory(memory_path)
        room = mem.get(room_hash)
        if room is None:
            return jsonify({"error": "not found"}), 404
        return jsonify(room)

    @app.route("/api/goal")
    def api_goal():
        from boukensha.goals.goal_manager import GoalManager
        gm = GoalManager(config_path)
        return jsonify(gm.read())

    @app.route("/api/sessions")
    def api_sessions():
        sessions_path.mkdir(parents=True, exist_ok=True)
        result = []
        for f in sorted(sessions_path.glob("*.jsonl"), reverse=True):
            meta = _parse_session_meta(f)
            result.append(meta)
        return jsonify(result)

    @app.route("/api/sessions/<session_id>")
    def api_session_detail(session_id: str):
        path = sessions_path / f"{session_id}.jsonl"
        if not path.exists():
            return jsonify({"error": "not found"}), 404
        entries = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return jsonify(entries)

    return app


def _parse_session_meta(path: Path) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "id": path.stem,
        "started_at": None,
        "model": None,
        "provider": None,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
    }
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        phase = event.get("phase")
        if phase == "session_start":
            meta["started_at"] = event.get("at")
            meta["model"] = event.get("model")
            meta["provider"] = event.get("provider")
        elif phase == "response":
            usage = event.get("usage") or {}
            meta["total_input_tokens"] += int(usage.get("input_tokens", 0))
            meta["total_output_tokens"] += int(usage.get("output_tokens", 0))
    return meta


def run_dashboard(app: Flask, *, port: int = 4568) -> threading.Thread:
    import logging
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)

    t = threading.Thread(
        target=lambda: app.run(port=port, threaded=True, use_reloader=False),
        daemon=True,
        name="boukensha-dashboard",
    )
    t.start()
    return t
