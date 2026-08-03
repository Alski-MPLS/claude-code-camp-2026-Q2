from boukensha.memory.item_stats import ItemStatsStore


def test_read_all_empty_when_no_file(tmp_path):
    store = ItemStatsStore(tmp_path)
    assert store.read_all() == {}


def test_save_and_get_round_trip(tmp_path):
    store = ItemStatsStore(tmp_path)
    store.save("a gold ring", {"wear_slot": "finger", "affects": {"ac": -10, "hitroll": 2}})
    result = store.get("a gold ring")
    assert result["wear_slot"] == "finger"
    assert result["affects"] == {"ac": -10, "hitroll": 2}
    assert "timestamp" in result


def test_get_is_case_insensitive(tmp_path):
    store = ItemStatsStore(tmp_path)
    store.save("A Gold Ring", {"wear_slot": "finger", "affects": {}})
    assert store.get("a gold ring") is not None
    assert store.get("A GOLD RING") is not None


def test_get_returns_none_for_unknown_item(tmp_path):
    store = ItemStatsStore(tmp_path)
    assert store.get("nonexistent") is None


def test_save_overwrites_existing_entry(tmp_path):
    store = ItemStatsStore(tmp_path)
    store.save("a gold ring", {"wear_slot": "finger", "affects": {"ac": -5}})
    store.save("a gold ring", {"wear_slot": "finger", "affects": {"ac": -10}})
    assert store.get("a gold ring")["affects"] == {"ac": -10}
    assert len(store.read_all()) == 1


def test_persists_across_instances(tmp_path):
    ItemStatsStore(tmp_path).save("a long sword", {"wear_slot": "wielded", "affects": {"hitroll": 1}})
    reloaded = ItemStatsStore(tmp_path).get("a long sword")
    assert reloaded["affects"] == {"hitroll": 1}


def test_atomic_write_no_partial_state(tmp_path):
    import os
    store = ItemStatsStore(tmp_path)
    store.save("a gold ring", {"wear_slot": "finger", "affects": {}})
    assert not any(f.endswith(".tmp") for f in os.listdir(tmp_path))
    assert (tmp_path / "item_stats.yaml").exists()
