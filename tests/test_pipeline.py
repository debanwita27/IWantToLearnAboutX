"""
test_pipeline.py — integration smoke test for the full run.py pipeline

All external calls (research, synthesize, send, git) are mocked.
Verifies the orchestration: state is read → pipeline runs → state advances → saved.
"""

import sys
import os
import json
import tempfile
import shutil
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))


def make_state(topic="consensus_algorithms", day=1):
    return {
        "_comment": "test",
        "current_week": "2026-19",
        "current_topic_id": topic,
        "current_day": day,
        "completed_topics": [],
        "queue": ["storage_engines", "distributed_transactions"],
    }


def make_digest(day=1):
    from synthesizer import DailyDigest
    return DailyDigest(
        topic_id="consensus_algorithms",
        topic_name="Consensus Algorithms",
        day=day,
        week="2026-19",
        nugget="Today's nugget content.",
        curated_links=[{"title": "Link", "url": "https://example.com", "depth_tag": "mid", "why": "why"}],
        reference_pick="Some book recommendation.",
        progress_bar=f"Day {day}/7 · Consensus Algorithms · depth-first",
        raw_bundle_context="raw context",
    )


def make_bundle(day=1):
    from researcher import ResearchBundle, Article
    return ResearchBundle(
        topic_id="consensus_algorithms",
        topic_name="Consensus Algorithms",
        day=day,
        depth_mode="depth_first",
        day_focus="Mental model",
        articles=[Article("Title", "https://example.com", "snippet", "Wikipedia", "surface")],
        taxonomy_references={"easy": ["Book"], "mid": ["Paper"], "deep": ["Thesis"], "niche": ["Blog"]},
    )


@pytest.fixture
def tmp_state(tmp_path):
    """Write a state file to a temp dir and patch STATE_PATH."""
    state_file = tmp_path / "progress.json"
    state_file.write_text(json.dumps(make_state()))
    return str(state_file)


def test_pipeline_day_increments(tmp_state):
    import run
    original_state_path = run.STATE_PATH
    run.STATE_PATH = tmp_state

    with patch("run.research", return_value=make_bundle(day=1)), \
         patch("run.synthesize", return_value=make_digest(day=1)), \
         patch("run.send", return_value=True), \
         patch("run.save_artifact", return_value="/tmp/day-1.md"):
        run.main()

    with open(tmp_state) as f:
        result = json.load(f)

    assert result["current_day"] == 2
    assert result["current_topic_id"] == "consensus_algorithms"
    run.STATE_PATH = original_state_path


def test_pipeline_topic_advances_after_day_7(tmp_state):
    import run
    original_state_path = run.STATE_PATH
    run.STATE_PATH = tmp_state

    with open(tmp_state, "w") as f:
        json.dump(make_state(day=7), f)

    with patch("run.research", return_value=make_bundle(day=7)), \
         patch("run.synthesize", return_value=make_digest(day=7)), \
         patch("run.send", return_value=True), \
         patch("run.save_artifact", return_value="/tmp/day-7.md"):
        run.main()

    with open(tmp_state) as f:
        result = json.load(f)

    assert result["current_day"] == 1
    assert result["current_topic_id"] == "storage_engines"
    assert "consensus_algorithms" in result["completed_topics"]
    assert "storage_engines" not in result["queue"]
    run.STATE_PATH = original_state_path


def test_pipeline_calls_research_with_correct_args(tmp_state):
    import run
    original_state_path = run.STATE_PATH
    run.STATE_PATH = tmp_state

    with open(tmp_state, "w") as f:
        json.dump(make_state(topic="ebpf", day=4), f)

    mock_research = MagicMock(return_value=make_bundle(day=4))

    with patch("run.research", mock_research), \
         patch("run.synthesize", return_value=make_digest(day=4)), \
         patch("run.send", return_value=True), \
         patch("run.save_artifact", return_value="/tmp/day-4.md"):
        run.main()

    mock_research.assert_called_once_with("ebpf", 4)
    run.STATE_PATH = original_state_path


def test_pipeline_calls_send(tmp_state):
    import run
    original_state_path = run.STATE_PATH
    run.STATE_PATH = tmp_state

    mock_send = MagicMock(return_value=True)

    with patch("run.research", return_value=make_bundle()), \
         patch("run.synthesize", return_value=make_digest()), \
         patch("run.send", mock_send), \
         patch("run.save_artifact", return_value="/tmp/day-1.md"):
        run.main()

    mock_send.assert_called_once()
    run.STATE_PATH = original_state_path


def test_pipeline_saves_artifact(tmp_state, tmp_path):
    import run
    original_state_path = run.STATE_PATH
    run.STATE_PATH = tmp_state

    mock_save = MagicMock(return_value=str(tmp_path / "day-1.md"))

    with patch("run.research", return_value=make_bundle()), \
         patch("run.synthesize", return_value=make_digest()), \
         patch("run.send", return_value=True), \
         patch("run.save_artifact", mock_save):
        run.main()

    mock_save.assert_called_once()
    run.STATE_PATH = original_state_path


def test_pipeline_email_failure_raises(tmp_state):
    import run
    original_state_path = run.STATE_PATH
    run.STATE_PATH = tmp_state

    with patch("run.research", return_value=make_bundle()), \
         patch("run.synthesize", return_value=make_digest()), \
         patch("run.send", side_effect=Exception("SMTP down")), \
         patch("run.save_artifact", return_value="/tmp/day-1.md"):
        with pytest.raises(Exception, match="SMTP down"):
            run.main()

    # State should NOT have advanced if email failed
    with open(tmp_state) as f:
        state = json.load(f)
    assert state["current_day"] == 1
    run.STATE_PATH = original_state_path
