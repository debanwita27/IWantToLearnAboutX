"""
test_state.py — tests for advance_state logic and state/progress.json integrity

Critical coverage:
- Day counter increments correctly days 1-6
- Topic advances at day 7 (pops queue, resets day to 1)
- THE BUG: completed topic must never reappear as current or in queue
- New current topic must not remain in queue (no future restart)
- Empty queue handled gracefully
- state/progress.json on disk is internally consistent
"""

import json
import sys
import os
import copy

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))
from run import advance_state

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")


# ── Fixtures ───────────────────────────────────────────────────────────────────

def make_state(current_topic="topic_a", current_day=1, queue=None, completed=None):
    return {
        "current_week": "2026-19",
        "current_topic_id": current_topic,
        "current_day": current_day,
        "completed_topics": completed or [],
        "queue": queue if queue is not None else ["topic_b", "topic_c"],
    }


# ── Day counter ────────────────────────────────────────────────────────────────

def test_day_increments_normally():
    for start_day in range(1, 7):
        state = make_state(current_day=start_day)
        result = advance_state(state)
        assert result["current_day"] == start_day + 1
        assert result["current_topic_id"] == "topic_a"


def test_day_does_not_increment_past_7_without_topic_change():
    # Day 7 should trigger topic change, not day 8
    state = make_state(current_day=7)
    result = advance_state(state)
    assert result["current_day"] == 1
    assert result["current_topic_id"] != "topic_a" or not result["queue"]


# ── Topic advancement at day 7 ─────────────────────────────────────────────────

def test_topic_advances_at_day_7():
    state = make_state(current_day=7, queue=["topic_b", "topic_c"])
    result = advance_state(state)
    assert result["current_topic_id"] == "topic_b"
    assert result["current_day"] == 1


def test_completed_topic_moved_to_completed_list():
    state = make_state(current_topic="topic_a", current_day=7, queue=["topic_b"])
    result = advance_state(state)
    assert "topic_a" in result["completed_topics"]


def test_queue_shrinks_after_topic_advance():
    state = make_state(current_day=7, queue=["topic_b", "topic_c", "topic_d"])
    result = advance_state(state)
    assert "topic_b" not in result["queue"]
    assert len(result["queue"]) == 2  # topic_c, topic_d remain


# ── THE BUG: completed topic must never restart ────────────────────────────────

def test_completed_topic_not_in_queue_after_advance():
    """The bug: consensus_algorithms was in queue[0] AND current_topic_id.
    After advance, it was popped from queue and set as current again."""
    state = make_state(
        current_topic="topic_a",
        current_day=7,
        queue=["topic_a", "topic_b", "topic_c"],  # topic_a duplicated in queue
    )
    result = advance_state(state)
    assert result["current_topic_id"] != "topic_a", (
        "Completed topic restarted — the queue duplication bug!"
    )
    assert "topic_a" not in result["queue"], (
        "Completed topic still lurking in queue"
    )


def test_completed_topic_not_current_after_advance():
    state = make_state(current_topic="alpha", current_day=7, queue=["alpha", "beta"])
    result = advance_state(state)
    assert result["current_topic_id"] == "beta"
    assert "alpha" in result["completed_topics"]
    assert "alpha" not in result["queue"]


def test_multiple_duplicates_in_queue_all_removed():
    state = make_state(
        current_topic="topic_a",
        current_day=7,
        queue=["topic_a", "topic_b", "topic_a", "topic_c"],
    )
    result = advance_state(state)
    assert "topic_a" not in result["queue"]
    assert result["current_topic_id"] == "topic_b"


# ── New current topic must not remain in queue ────────────────────────────────

def test_new_current_topic_removed_from_queue():
    """After advancing, the new current_topic_id must not also be in queue
    (or it will restart next time this topic completes)."""
    state = make_state(
        current_topic="topic_a",
        current_day=7,
        queue=["topic_b", "topic_b", "topic_c"],  # topic_b duplicated
    )
    result = advance_state(state)
    assert result["current_topic_id"] == "topic_b"
    assert "topic_b" not in result["queue"], (
        "New current topic still in queue — will restart after its week"
    )


def test_next_topic_queue_is_clean():
    state = make_state(current_day=7, queue=["topic_b", "topic_c", "topic_d"])
    result = advance_state(state)
    current = result["current_topic_id"]
    assert current not in result["queue"]


# ── Empty queue ────────────────────────────────────────────────────────────────

def test_empty_queue_handled_gracefully():
    state = make_state(current_day=7, queue=[])
    # Should not raise
    result = advance_state(state)
    assert result["current_day"] == 1


# ── Full week simulation ───────────────────────────────────────────────────────

def test_full_week_cycle():
    """Simulate 7 days → topic changes → 7 more days → next topic changes."""
    state = make_state(
        current_topic="topic_a",
        current_day=1,
        queue=["topic_b", "topic_c"],
    )
    for day in range(1, 7):
        state = advance_state(state)
    assert state["current_day"] == 7
    assert state["current_topic_id"] == "topic_a"

    # Day 7 — advance to next topic
    state = advance_state(state)
    assert state["current_topic_id"] == "topic_b"
    assert state["current_day"] == 1
    assert "topic_a" in state["completed_topics"]
    assert "topic_b" not in state["queue"]

    # Another full week on topic_b
    for _ in range(6):
        state = advance_state(state)
    state = advance_state(state)

    assert state["current_topic_id"] == "topic_c"
    assert state["current_day"] == 1
    assert "topic_b" in state["completed_topics"]
    assert "topic_c" not in state["queue"]


# ── state/progress.json on-disk integrity ─────────────────────────────────────

def test_progress_json_current_topic_not_in_queue():
    """The current_topic_id must never appear in the queue."""
    path = os.path.join(REPO_ROOT, "state", "progress.json")
    with open(path) as f:
        state = json.load(f)
    current = state["current_topic_id"]
    assert current not in state["queue"], (
        f"current_topic_id '{current}' is also in queue — restart bug waiting to happen"
    )


def test_progress_json_no_duplicate_queue_entries():
    path = os.path.join(REPO_ROOT, "state", "progress.json")
    with open(path) as f:
        state = json.load(f)
    queue = state["queue"]
    assert len(queue) == len(set(queue)), (
        f"Duplicate entries in queue: {[t for t in queue if queue.count(t) > 1]}"
    )


def test_progress_json_required_fields():
    path = os.path.join(REPO_ROOT, "state", "progress.json")
    with open(path) as f:
        state = json.load(f)
    for field in ["current_topic_id", "current_day", "current_week", "queue", "completed_topics"]:
        assert field in state, f"Missing field '{field}' in progress.json"


def test_progress_json_day_in_valid_range():
    path = os.path.join(REPO_ROOT, "state", "progress.json")
    with open(path) as f:
        state = json.load(f)
    assert 1 <= state["current_day"] <= 7, f"current_day={state['current_day']} out of range"


def test_progress_json_completed_topics_not_in_queue():
    path = os.path.join(REPO_ROOT, "state", "progress.json")
    with open(path) as f:
        state = json.load(f)
    for topic in state["completed_topics"]:
        assert topic not in state["queue"], (
            f"Completed topic '{topic}' still in queue"
        )
