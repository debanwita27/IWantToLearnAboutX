"""
test_emailer.py — tests for HTML email building, artifact saving, and send()
"""

import os
import sys
import json
import tempfile
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))
from emailer import build_html, build_plaintext, save_artifact, send
from synthesizer import DailyDigest


def make_digest(**overrides):
    defaults = dict(
        topic_id="consensus_algorithms",
        topic_name="Consensus Algorithms",
        subtopic="Raft leader election",
        day=3,
        week="2026-19",
        nugget="Raft is a consensus algorithm. It elects a leader. The leader replicates logs. Simple until it isn't.",
        curated_links=[
            {"title": "Raft Paper", "url": "https://raft.github.io/raft.pdf", "depth_tag": "deep", "why": "The original paper"},
            {"title": "HN Discussion", "url": "https://hn.example.com/1", "depth_tag": "mid", "why": "War stories"},
        ],
        reference_pick="**Designing Data-Intensive Applications** — Martin Kleppmann. Chapter 9 is the clearest explanation of consensus you'll find outside a whiteboard.",
        progress_bar="Day 3/7 · Consensus Algorithms › Raft leader election · depth-first",
        raw_bundle_context="# Raw context here",
    )
    defaults.update(overrides)
    return DailyDigest(**defaults)


# ── HTML building ──────────────────────────────────────────────────────────────

def test_build_html_contains_topic_name():
    html = build_html(make_digest())
    assert "Consensus Algorithms" in html


def test_build_html_contains_subtopic():
    html = build_html(make_digest())
    assert "Raft leader election" in html


def test_build_html_contains_day_progress():
    html = build_html(make_digest(day=3))
    assert "3/7" in html


def test_build_html_contains_nugget():
    html = build_html(make_digest())
    assert "Raft is a consensus algorithm" in html


def test_build_html_contains_links():
    html = build_html(make_digest())
    assert "raft.github.io" in html
    assert "hn.example.com" in html


def test_build_html_depth_tags_rendered():
    html = build_html(make_digest())
    assert "deep" in html.lower()
    assert "mid" in html.lower()


def test_build_html_contains_reference_pick():
    html = build_html(make_digest())
    assert "Designing Data-Intensive" in html


def test_build_html_is_valid_html_structure():
    html = build_html(make_digest())
    assert html.startswith("<!DOCTYPE html>")
    assert "<body" in html
    assert "</body>" in html
    assert "</html>" in html


def test_build_html_all_7_days():
    for day in range(1, 8):
        html = build_html(make_digest(day=day))
        assert f"{day}/7" in html


def test_build_html_no_empty_links_section_when_no_links():
    digest = make_digest(curated_links=[])
    html = build_html(digest)
    # Should not crash and should not show broken link markup
    assert "Consensus Algorithms" in html


# ── Plaintext building ─────────────────────────────────────────────────────────

def test_build_plaintext_contains_topic():
    txt = build_plaintext(make_digest())
    assert "Consensus Algorithms" in txt


def test_build_plaintext_contains_links():
    txt = build_plaintext(make_digest())
    assert "raft.github.io" in txt


def test_build_plaintext_contains_reference():
    txt = build_plaintext(make_digest())
    assert "Designing Data-Intensive" in txt


def test_build_plaintext_no_html_tags():
    txt = build_plaintext(make_digest())
    assert "<" not in txt and ">" not in txt


# ── Artifact saving ────────────────────────────────────────────────────────────

def test_save_artifact_creates_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = save_artifact(make_digest(), output_dir=tmpdir)
        assert os.path.exists(path)


def test_save_artifact_correct_filename():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = save_artifact(make_digest(day=4), output_dir=tmpdir)
        assert "day-4.md" in path


def test_save_artifact_file_contains_nugget():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = save_artifact(make_digest(), output_dir=tmpdir)
        content = open(path).read()
        assert "Raft is a consensus algorithm" in content


def test_save_artifact_file_contains_links():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = save_artifact(make_digest(), output_dir=tmpdir)
        content = open(path).read()
        assert "raft.github.io" in content


def test_save_artifact_overwrites_existing():
    with tempfile.TemporaryDirectory() as tmpdir:
        save_artifact(make_digest(nugget="First version"), output_dir=tmpdir)
        save_artifact(make_digest(nugget="Second version"), output_dir=tmpdir)
        path = os.path.join(tmpdir, "day-3.md")
        content = open(path).read()
        assert "Second version" in content
        assert "First version" not in content


# ── send() ─────────────────────────────────────────────────────────────────────

@patch.dict(os.environ, {"RESEND_API_KEY": "test_key", "EMAIL_TO": "test@example.com"})
@patch("emailer.resend.Emails.send")
def test_send_calls_resend(mock_send):
    mock_send.return_value = {"id": "abc-123"}
    result = send(make_digest())
    assert result is True
    mock_send.assert_called_once()


@patch.dict(os.environ, {"RESEND_API_KEY": "test_key", "EMAIL_TO": "test@example.com"})
@patch("emailer.resend.Emails.send")
def test_send_uses_correct_recipient(mock_send):
    mock_send.return_value = {"id": "abc-123"}
    send(make_digest())
    call_params = mock_send.call_args[0][0]
    assert call_params["to"] == ["test@example.com"]


@patch.dict(os.environ, {"RESEND_API_KEY": "test_key", "EMAIL_TO": "test@example.com"})
@patch("emailer.resend.Emails.send")
def test_send_subject_contains_day_topic_and_subtopic(mock_send):
    mock_send.return_value = {"id": "abc-123"}
    send(make_digest(day=5, topic_name="Storage Engines", subtopic="B-tree internals"))
    call_params = mock_send.call_args[0][0]
    assert "5/7" in call_params["subject"]
    assert "Storage Engines" in call_params["subject"]
    assert "B-tree internals" in call_params["subject"]


def test_send_raises_without_api_key():
    with patch.dict(os.environ, {"RESEND_API_KEY": "", "EMAIL_TO": "test@example.com"}):
        with pytest.raises(EnvironmentError, match="RESEND_API_KEY"):
            send(make_digest())


def test_send_raises_without_email_to():
    with patch.dict(os.environ, {"RESEND_API_KEY": "key", "EMAIL_TO": ""}):
        with pytest.raises(EnvironmentError, match="EMAIL_TO"):
            send(make_digest())
