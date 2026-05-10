"""
test_state.py — tests for the round-robin rotation advance_state logic
and state/progress.json on-disk integrity.

Rotation model:
- All topics live in `rotation` (ordered list).
- `rotation_pos` advances each week (wraps around).
- On wrap: every topic advances to its next subtopic index.
- Topics that exhaust all subtopics + niche_topics retire to completed_topics.
"""

import json
import sys
import os
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))
from run import advance_state

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")

# Fake taxonomy used by _subtopic_count inside advance_state.
# Each topic has 2 subtopics + 2 niche_topics = 4 total sub-passes.
FAKE_SUBTOPIC_COUNT = 4


def _patch_count(n=FAKE_SUBTOPIC_COUNT):
    """Patch _subtopic_count so tests don't need a real taxonomy file."""
    return patch("run._subtopic_count", return_value=n)


def make_state(rotation=None, rotation_pos=0, subtopic_progress=None,
               current_day=1, completed=None):
    if rotation is None:
        rotation = ["topic_a", "topic_b", "topic_c"]
    if subtopic_progress is None:
        subtopic_progress = {t: 0 for t in rotation}
    return {
        "current_week": "2026-19",
        "current_day": current_day,
        "rotation": list(rotation),
        "rotation_pos": rotation_pos,
        "subtopic_progress": dict(subtopic_progress),
        "completed_topics": list(completed or []),
    }


# ── Day counter ────────────────────────────────────────────────────────────────

def test_day_increments_days_1_to_6():
    with _patch_count():
        for start in range(1, 7):
            state = make_state(current_day=start)
            result = advance_state(state)
            assert result["current_day"] == start + 1
            assert result["rotation_pos"] == 0  # topic unchanged


def test_day_7_triggers_rotation():
    with _patch_count():
        state = make_state(current_day=7)
        result = advance_state(state)
        assert result["current_day"] == 1
        assert result["rotation_pos"] == 1  # moved to topic_b


# ── rotation_pos advancement ───────────────────────────────────────────────────

def test_rotation_pos_advances_each_week():
    with _patch_count():
        state = make_state(rotation_pos=0, current_day=7)
        state = advance_state(state)
        assert state["rotation_pos"] == 1

        state["current_day"] = 7
        state = advance_state(state)
        assert state["rotation_pos"] == 2


def test_rotation_pos_wraps_at_end():
    with _patch_count():
        # rotation has 3 topics; pos 2 → wraps to 0
        state = make_state(rotation_pos=2, current_day=7)
        result = advance_state(state)
        assert result["rotation_pos"] == 0


# ── subtopic_progress on full-pass wrap ───────────────────────────────────────

def test_subtopic_progress_increments_on_wrap():
    with _patch_count(n=4):
        state = make_state(rotation_pos=2, current_day=7)  # last topic → wrap
        result = advance_state(state)
        for topic_id in result["rotation"]:
            assert result["subtopic_progress"][topic_id] == 1


def test_subtopic_progress_does_not_increment_mid_rotation():
    with _patch_count(n=4):
        state = make_state(rotation_pos=0, current_day=7)  # not yet wrapping
        result = advance_state(state)
        # Still on rotation pass 1; no topic advanced to sub 1 yet
        for topic_id in result["rotation"]:
            assert result["subtopic_progress"][topic_id] == 0


# ── topic exhaustion and completion ───────────────────────────────────────────

def test_exhausted_topic_removed_from_rotation():
    with _patch_count(n=1):
        # Each topic has only 1 sub; after one full pass they're all done
        state = make_state(rotation_pos=2, current_day=7)
        result = advance_state(state)
        assert result["rotation"] == []
        assert set(result["completed_topics"]) == {"topic_a", "topic_b", "topic_c"}


def test_only_exhausted_topics_removed():
    # topic_a has 2 subs, topic_b has 1 (exhausted after 1 pass), topic_c has 2
    def count_for(topic_id):
        return 1 if topic_id == "topic_b" else 2

    with patch("run._subtopic_count", side_effect=count_for):
        state = make_state(
            rotation=["topic_a", "topic_b", "topic_c"],
            rotation_pos=2,       # full pass completing
            subtopic_progress={"topic_a": 0, "topic_b": 0, "topic_c": 0},
            current_day=7,
        )
        result = advance_state(state)
        assert "topic_b" not in result["rotation"]
        assert "topic_b" in result["completed_topics"]
        assert "topic_a" in result["rotation"]
        assert "topic_c" in result["rotation"]


def test_exhausted_topic_removed_from_subtopic_progress():
    with _patch_count(n=1):
        state = make_state(rotation_pos=2, current_day=7)
        result = advance_state(state)
        for tid in result["completed_topics"]:
            assert tid not in result["subtopic_progress"]


# ── Full rotation simulation ───────────────────────────────────────────────────

def test_full_rotation_two_topics_two_subs():
    """
    2 topics × 2 subtopics × 7 days each = 28 total daily steps.
    After each 7 days one step of this plays out:
      Week 1: topic_a sub0 → rotation_pos 1
      Week 2: topic_b sub0 → wrap → both advance to sub1
      Week 3: topic_a sub1 → rotation_pos 1
      Week 4: topic_b sub1 → wrap → both exhausted → completed
    """
    with _patch_count(n=2):
        state = make_state(
            rotation=["topic_a", "topic_b"],
            rotation_pos=0,
            subtopic_progress={"topic_a": 0, "topic_b": 0},
            current_day=1,
        )

        # 6 days of topic_a sub0
        for _ in range(6):
            state = advance_state(state)
        assert state["rotation_pos"] == 0
        assert state["current_day"] == 7

        # Day 7: advance to topic_b sub0
        state = advance_state(state)
        assert state["rotation_pos"] == 1
        assert state["subtopic_progress"]["topic_a"] == 0  # no increment yet

        # Days 1–7 of topic_b sub0 (wraps rotation → both go to sub1)
        for _ in range(6):
            state["current_day"] = state["current_day"] if state["current_day"] < 7 else 1
            state = advance_state(state)
        state = advance_state(state)  # day 7 of topic_b → wrap
        assert state["rotation_pos"] == 0
        assert state["subtopic_progress"].get("topic_a", 0) == 1
        assert state["subtopic_progress"].get("topic_b", 0) == 1

        # Now both topics are on sub1. Run topic_a sub1 for 7 days.
        for _ in range(6):
            state = advance_state(state)
        state = advance_state(state)
        assert state["rotation_pos"] == 1  # moved to topic_b sub1

        # Run topic_b sub1 for 7 days → wrap → both exhausted
        for _ in range(6):
            state = advance_state(state)
        state = advance_state(state)
        assert set(state["completed_topics"]) == {"topic_a", "topic_b"}
        assert state["rotation"] == []


# ── progress.json on-disk integrity ───────────────────────────────────────────

def test_progress_json_required_fields():
    path = os.path.join(REPO_ROOT, "state", "progress.json")
    with open(path) as f:
        state = json.load(f)
    for field in ["current_day", "current_week", "rotation", "rotation_pos",
                  "subtopic_progress", "completed_topics"]:
        assert field in state, f"Missing field '{field}' in progress.json"


def test_progress_json_day_in_valid_range():
    path = os.path.join(REPO_ROOT, "state", "progress.json")
    with open(path) as f:
        state = json.load(f)
    assert 1 <= state["current_day"] <= 7


def test_progress_json_rotation_pos_in_bounds():
    path = os.path.join(REPO_ROOT, "state", "progress.json")
    with open(path) as f:
        state = json.load(f)
    rotation = state["rotation"]
    pos = state["rotation_pos"]
    assert 0 <= pos < len(rotation), (
        f"rotation_pos {pos} out of bounds for rotation of length {len(rotation)}"
    )


def test_progress_json_no_duplicate_rotation_entries():
    path = os.path.join(REPO_ROOT, "state", "progress.json")
    with open(path) as f:
        state = json.load(f)
    rotation = state["rotation"]
    assert len(rotation) == len(set(rotation)), (
        f"Duplicate entries in rotation: {[t for t in rotation if rotation.count(t) > 1]}"
    )


def test_progress_json_all_rotation_topics_have_subtopic_progress():
    path = os.path.join(REPO_ROOT, "state", "progress.json")
    with open(path) as f:
        state = json.load(f)
    missing = [t for t in state["rotation"] if t not in state["subtopic_progress"]]
    assert not missing, f"Topics in rotation missing from subtopic_progress: {missing}"


def test_progress_json_completed_topics_not_in_rotation():
    path = os.path.join(REPO_ROOT, "state", "progress.json")
    with open(path) as f:
        state = json.load(f)
    overlap = set(state["completed_topics"]) & set(state["rotation"])
    assert not overlap, f"Topics in both completed_topics and rotation: {overlap}"
