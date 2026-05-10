"""
test_pipeline.py — integration smoke test for the full run.py pipeline
with round-robin rotation state.

All external calls (research, synthesize, send, git) are mocked.
"""

import sys
import os
import json
import tempfile
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))


FAKE_SUBTOPIC_COUNT = 4


def _patch_count(n=FAKE_SUBTOPIC_COUNT):
    return patch("run._subtopic_count", return_value=n)


def make_state(rotation=None, rotation_pos=0, subtopic_progress=None, day=1):
    if rotation is None:
        rotation = ["topic_a", "topic_b", "topic_c"]
    if subtopic_progress is None:
        subtopic_progress = {t: 0 for t in rotation}
    return {
        "_comment": "test",
        "current_week": "2026-19",
        "current_day": day,
        "rotation": list(rotation),
        "rotation_pos": rotation_pos,
        "subtopic_progress": dict(subtopic_progress),
        "completed_topics": [],
    }


def make_digest(day=1, subtopic="Raft leader election"):
    from synthesizer import DailyDigest
    return DailyDigest(
        topic_id="topic_a",
        topic_name="Topic A",
        subtopic=subtopic,
        day=day,
        week="2026-19",
        nugget="Today's nugget content.",
        curated_links=[{"title": "Link", "url": "https://example.com", "depth_tag": "mid", "why": "why"}],
        reference_pick="Some book recommendation.",
        progress_bar=f"Day {day}/7 · Topic A › {subtopic} · depth-first",
        raw_bundle_context="raw context",
    )


def make_bundle(day=1, subtopic="Raft leader election"):
    from researcher import ResearchBundle, Article
    return ResearchBundle(
        topic_id="topic_a",
        topic_name="Topic A",
        subtopic=subtopic,
        day=day,
        depth_mode="depth_first",
        day_focus="Mental model",
        articles=[Article("Title", "https://example.com", "snippet", "Wikipedia", "surface")],
        taxonomy_references={"easy": ["Book"], "mid": ["Paper"], "deep": ["Thesis"], "niche": ["Blog"]},
    )


@pytest.fixture
def tmp_state(tmp_path):
    state_file = tmp_path / "progress.json"
    state_file.write_text(json.dumps(make_state()))
    return str(state_file)


def test_pipeline_day_increments(tmp_state):
    import run
    original = run.STATE_PATH
    run.STATE_PATH = tmp_state

    with _patch_count(), \
         patch("run.research", return_value=make_bundle(day=1)), \
         patch("run.synthesize", return_value=make_digest(day=1)), \
         patch("run.send", return_value=True), \
         patch("run.save_artifact", return_value="/tmp/day-1.md"):
        run.main()

    with open(tmp_state) as f:
        result = json.load(f)

    assert result["current_day"] == 2
    assert result["rotation_pos"] == 0  # still on topic_a
    run.STATE_PATH = original


def test_pipeline_rotation_advances_after_day_7(tmp_state):
    import run
    original = run.STATE_PATH
    run.STATE_PATH = tmp_state

    with open(tmp_state, "w") as f:
        json.dump(make_state(day=7), f)

    with _patch_count(), \
         patch("run.research", return_value=make_bundle(day=7)), \
         patch("run.synthesize", return_value=make_digest(day=7)), \
         patch("run.send", return_value=True), \
         patch("run.save_artifact", return_value="/tmp/day-7.md"):
        run.main()

    with open(tmp_state) as f:
        result = json.load(f)

    assert result["current_day"] == 1
    assert result["rotation_pos"] == 1  # moved to topic_b
    assert result["subtopic_progress"]["topic_a"] == 0  # not yet wrapped
    run.STATE_PATH = original


def test_pipeline_subtopic_advances_on_full_pass(tmp_state):
    """When the last topic in rotation finishes day 7, all subtopic_progress +1."""
    import run
    original = run.STATE_PATH
    run.STATE_PATH = tmp_state

    # rotation_pos=2 = last topic; day 7 → wrap
    with open(tmp_state, "w") as f:
        json.dump(make_state(rotation_pos=2, day=7), f)

    with _patch_count(n=4), \
         patch("run.research", return_value=make_bundle(day=7)), \
         patch("run.synthesize", return_value=make_digest(day=7)), \
         patch("run.send", return_value=True), \
         patch("run.save_artifact", return_value="/tmp/day-7.md"):
        run.main()

    with open(tmp_state) as f:
        result = json.load(f)

    assert result["rotation_pos"] == 0
    for t in result["rotation"]:
        assert result["subtopic_progress"][t] == 1
    run.STATE_PATH = original


def test_pipeline_calls_research_with_topic_and_subtopic(tmp_state):
    import run
    original = run.STATE_PATH
    run.STATE_PATH = tmp_state

    mock_research = MagicMock(return_value=make_bundle(day=1))

    with _patch_count(), \
         patch("run.research", mock_research), \
         patch("run.synthesize", return_value=make_digest()), \
         patch("run.send", return_value=True), \
         patch("run.save_artifact", return_value="/tmp/day-1.md"):
        run.main()

    args, kwargs = mock_research.call_args
    assert args[0] == "topic_a"
    assert args[1] == 1
    assert kwargs.get("subtopic_idx", args[2] if len(args) > 2 else 0) == 0
    run.STATE_PATH = original


def test_pipeline_calls_send(tmp_state):
    import run
    original = run.STATE_PATH
    run.STATE_PATH = tmp_state

    mock_send = MagicMock(return_value=True)

    with _patch_count(), \
         patch("run.research", return_value=make_bundle()), \
         patch("run.synthesize", return_value=make_digest()), \
         patch("run.send", mock_send), \
         patch("run.save_artifact", return_value="/tmp/day-1.md"):
        run.main()

    mock_send.assert_called_once()
    run.STATE_PATH = original


def test_pipeline_email_failure_does_not_advance_state(tmp_state):
    import run
    original = run.STATE_PATH
    run.STATE_PATH = tmp_state

    with _patch_count(), \
         patch("run.research", return_value=make_bundle()), \
         patch("run.synthesize", return_value=make_digest()), \
         patch("run.send", side_effect=Exception("SMTP down")), \
         patch("run.save_artifact", return_value="/tmp/day-1.md"):
        with pytest.raises(Exception, match="SMTP down"):
            run.main()

    with open(tmp_state) as f:
        state = json.load(f)
    assert state["current_day"] == 1  # not advanced
    run.STATE_PATH = original
