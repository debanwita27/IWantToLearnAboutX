"""
test_researcher.py — tests for the research fetcher functions

HTTP calls are mocked so tests run without network or API keys.
"""

import sys
import os
import json
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))
from researcher import (
    fetch_wikipedia,
    fetch_hackernews,
    fetch_arxiv,
    fetch_reddit,
    fetch_internet_archive,
    get_day_focus,
    build_search_queries,
    load_topic,
    ResearchBundle,
    research,
)


# ── get_day_focus ──────────────────────────────────────────────────────────────

def test_get_day_focus_depth_first_day1():
    focus = get_day_focus(1, "depth_first")
    assert "stack" in focus.lower() or "mental" in focus.lower()


def test_get_day_focus_breadth_first_day1():
    focus = get_day_focus(1, "breadth_first")
    assert "overview" in focus.lower() or "matter" in focus.lower()


def test_get_day_focus_all_days_have_content():
    for day in range(1, 8):
        for mode in ("depth_first", "breadth_first"):
            focus = get_day_focus(day, mode)
            assert isinstance(focus, str) and len(focus) > 5


def test_depth_and_breadth_arcs_differ():
    for day in range(1, 8):
        assert get_day_focus(day, "depth_first") != get_day_focus(day, "breadth_first")


# ── build_search_queries ───────────────────────────────────────────────────────

def test_build_search_queries_returns_list():
    topic = {"name": "Raft", "subtopics": ["leader election", "log replication"], "niche_topics": ["Multi-Raft"]}
    queries = build_search_queries(topic, day=1, depth_mode="depth_first", subtopic_idx=0)
    assert isinstance(queries, list)
    assert len(queries) >= 1
    # Primary query should incorporate the topic and subtopic
    assert any("Raft" in q or "leader election" in q for q in queries)


def test_build_search_queries_focuses_on_current_subtopic():
    topic = {"name": "Raft", "subtopics": ["leader election", "log replication"], "niche_topics": ["Multi-Raft"]}
    q0 = build_search_queries(topic, day=1, depth_mode="depth_first", subtopic_idx=0)
    q1 = build_search_queries(topic, day=1, depth_mode="depth_first", subtopic_idx=1)
    # Different subtopics → different queries
    assert q0 != q1
    assert any("leader election" in q for q in q0)
    assert any("log replication" in q for q in q1)


def test_build_search_queries_niche_subtopic_via_idx():
    topic = {"name": "Raft", "subtopics": ["leader election"], "niche_topics": ["Multi-Raft", "EPaxos"]}
    # subtopic_idx=1 → first niche topic
    queries = build_search_queries(topic, day=3, depth_mode="depth_first", subtopic_idx=1)
    assert any("Multi-Raft" in q for q in queries)


def test_build_search_queries_day5_uses_internals_angle():
    topic = {"name": "Raft", "subtopics": ["leader election"], "niche_topics": []}
    queries = build_search_queries(topic, day=5, depth_mode="depth_first", subtopic_idx=0)
    assert any("internals" in q or "implementation" in q for q in queries)


# ── load_topic ─────────────────────────────────────────────────────────────────

def test_load_topic_returns_correct_topic():
    topic = load_topic("consensus_algorithms")
    assert topic["id"] == "consensus_algorithms"
    assert "_depth_mode" in topic
    assert topic["_depth_mode"] == "depth_first"


def test_load_topic_nonexistent_raises():
    with pytest.raises(ValueError, match="not found"):
        load_topic("this_topic_does_not_exist_xyz")


def test_load_topic_has_references():
    topic = load_topic("consensus_algorithms")
    refs = topic.get("references", {})
    assert "easy" in refs and "deep" in refs


# ── fetch_wikipedia ────────────────────────────────────────────────────────────

def _mock_wikipedia_responses(requests_mock):
    """Set up two-step Wikipedia mock: search then summary."""
    search_resp = MagicMock()
    search_resp.status_code = 200
    search_resp.json.return_value = {
        "query": {"search": [{"title": "Raft (algorithm)"}]}
    }
    summary_resp = MagicMock()
    summary_resp.status_code = 200
    summary_resp.json.return_value = {
        "title": "Raft (algorithm)",
        "extract": "Raft is a consensus algorithm designed to be easy to understand.",
        "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Raft_(algorithm)"}},
    }
    # First call = search, second = summary
    requests_mock.side_effect = [search_resp, summary_resp]


@patch("researcher.requests.get")
def test_fetch_wikipedia_returns_article(mock_get):
    _mock_wikipedia_responses(mock_get)
    results = fetch_wikipedia("Raft consensus")
    assert len(results) == 1
    assert results[0].source == "Wikipedia"
    assert results[0].depth_tag == "surface"
    assert "Raft" in results[0].title


@patch("researcher.requests.get")
def test_fetch_wikipedia_empty_search_returns_empty(mock_get):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"query": {"search": []}}
    mock_get.return_value = resp
    assert fetch_wikipedia("xyzzy_nonexistent_topic_abc") == []


@patch("researcher.requests.get")
def test_fetch_wikipedia_network_error_returns_empty(mock_get):
    mock_get.side_effect = Exception("network down")
    assert fetch_wikipedia("anything") == []


# ── fetch_hackernews ───────────────────────────────────────────────────────────

@patch("researcher.requests.get")
def test_fetch_hackernews_returns_articles(mock_get):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "hits": [
            {"title": "Understanding Raft", "url": "https://example.com/raft", "story_text": "Deep dive into Raft.", "objectID": "123"},
            {"title": "Paxos explained", "url": "https://example.com/paxos", "story_text": None, "objectID": "456"},
        ]
    }
    mock_get.return_value = resp
    results = fetch_hackernews("raft consensus", max_results=2)
    assert len(results) == 2
    assert all(a.source == "HackerNews" for a in results)
    assert all(a.depth_tag == "mid" for a in results)


@patch("researcher.requests.get")
def test_fetch_hackernews_handles_missing_url(mock_get):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "hits": [{"title": "No URL post", "url": None, "story_text": "text", "objectID": "999"}]
    }
    mock_get.return_value = resp
    results = fetch_hackernews("test")
    assert len(results) == 1
    assert "999" in results[0].url  # falls back to HN item URL


@patch("researcher.requests.get")
def test_fetch_hackernews_network_error_returns_empty(mock_get):
    mock_get.side_effect = Exception("timeout")
    assert fetch_hackernews("test") == []


# ── fetch_arxiv ────────────────────────────────────────────────────────────────

ARXIV_SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>In Search of an Understandable Consensus Algorithm</title>
    <id>https://arxiv.org/abs/1404.0253</id>
    <summary>Raft is a consensus algorithm designed to be more understandable than Paxos.</summary>
  </entry>
</feed>"""


@patch("researcher.requests.get")
def test_fetch_arxiv_parses_xml(mock_get):
    resp = MagicMock()
    resp.status_code = 200
    resp.text = ARXIV_SAMPLE_XML
    mock_get.return_value = resp
    results = fetch_arxiv("Raft consensus", max_results=1)
    assert len(results) == 1
    assert results[0].source == "arXiv"
    assert results[0].depth_tag == "deep"
    # The title or snippet should reference Raft (the XML fixture has both)
    assert "Raft" in results[0].title or "Raft" in results[0].snippet


@patch("researcher.requests.get")
def test_fetch_arxiv_network_error_returns_empty(mock_get):
    mock_get.side_effect = Exception("timeout")
    assert fetch_arxiv("anything") == []


# ── fetch_internet_archive ─────────────────────────────────────────────────────

@patch("researcher.requests.get")
def test_fetch_internet_archive_returns_articles(mock_get):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "response": {
            "docs": [
                {"identifier": "raft-paper", "title": "Raft Paper 1996", "description": "Old doc"},
            ]
        }
    }
    mock_get.return_value = resp
    results = fetch_internet_archive("raft", max_results=1)
    assert len(results) == 1
    assert results[0].source == "Internet Archive"
    assert results[0].depth_tag == "rabbit_hole"


# ── research() orchestrator ────────────────────────────────────────────────────

@patch("researcher.fetch_youtube_transcripts", return_value=[])
@patch("researcher.fetch_rss_feeds", return_value=[])
@patch("researcher.fetch_reddit", return_value=[])
@patch("researcher.fetch_core", return_value=[])
@patch("researcher.fetch_semantic_scholar", return_value=[])
@patch("researcher.fetch_arxiv", return_value=[])
@patch("researcher.fetch_hackernews", return_value=[])
@patch("researcher.fetch_wikipedia")
def test_research_returns_bundle(
    mock_wiki, mock_hn, mock_arxiv, mock_s2, mock_core,
    mock_reddit, mock_rss, mock_yt
):
    from researcher import Article
    mock_wiki.return_value = [
        Article(title="Wiki Raft", url="https://en.wikipedia.org/wiki/Raft", snippet="About Raft", source="Wikipedia", depth_tag="surface")
    ]
    mock_hn.return_value = [
        Article(title="HN Raft post", url="https://hn.example.com/1", snippet="HN post", source="HackerNews", depth_tag="mid")
    ]
    bundle = research("consensus_algorithms", day=1, subtopic_idx=0)
    assert isinstance(bundle, ResearchBundle)
    assert bundle.topic_id == "consensus_algorithms"
    assert bundle.day == 1
    assert bundle.depth_mode == "depth_first"
    assert bundle.subtopic != ""   # subtopic resolved from taxonomy
    assert len(bundle.articles) >= 1


@patch("researcher.fetch_youtube_transcripts", return_value=[])
@patch("researcher.fetch_rss_feeds", return_value=[])
@patch("researcher.fetch_reddit", return_value=[])
@patch("researcher.fetch_core", return_value=[])
@patch("researcher.fetch_semantic_scholar", return_value=[])
@patch("researcher.fetch_arxiv", return_value=[])
@patch("researcher.fetch_hackernews", return_value=[])
@patch("researcher.fetch_wikipedia")
def test_research_subtopic_idx_resolves_correctly(
    mock_wiki, mock_hn, mock_arxiv, mock_s2, mock_core,
    mock_reddit, mock_rss, mock_yt
):
    mock_wiki.return_value = []
    mock_hn.return_value = []
    bundle0 = research("consensus_algorithms", day=1, subtopic_idx=0)
    bundle1 = research("consensus_algorithms", day=1, subtopic_idx=1)
    assert bundle0.subtopic != bundle1.subtopic


@patch("researcher.fetch_youtube_transcripts", return_value=[])
@patch("researcher.fetch_rss_feeds", return_value=[])
@patch("researcher.fetch_reddit", return_value=[])
@patch("researcher.fetch_core", return_value=[])
@patch("researcher.fetch_semantic_scholar", return_value=[])
@patch("researcher.fetch_arxiv", return_value=[])
@patch("researcher.fetch_hackernews", return_value=[])
@patch("researcher.fetch_wikipedia", return_value=[])
def test_research_deduplicates_urls(*mocks):
    """Even if multiple sources return the same URL, bundle should deduplicate."""
    from researcher import Article
    from unittest.mock import patch as p
    with p("researcher.fetch_wikipedia") as mw, p("researcher.fetch_hackernews") as mh:
        dupe_url = "https://example.com/same"
        mw.return_value = [Article("T1", dupe_url, "s", "Wikipedia", "surface")]
        mh.return_value = [Article("T2", dupe_url, "s", "HN", "mid")]
        with p("researcher.fetch_arxiv", return_value=[]), \
             p("researcher.fetch_semantic_scholar", return_value=[]), \
             p("researcher.fetch_core", return_value=[]), \
             p("researcher.fetch_reddit", return_value=[]), \
             p("researcher.fetch_rss_feeds", return_value=[]), \
             p("researcher.fetch_youtube_transcripts", return_value=[]):
            bundle = research("consensus_algorithms", day=1, subtopic_idx=0)
        urls = [a.url for a in bundle.articles]
        assert len(urls) == len(set(urls)), "Duplicate URLs in research bundle"


def test_research_bundle_context_string_is_readable():
    from researcher import Article, ResearchBundle
    bundle = ResearchBundle(
        topic_id="test",
        topic_name="Test Topic",
        subtopic="Raft leader election",
        day=3,
        depth_mode="depth_first",
        day_focus="Internal mechanics",
        articles=[Article("Title A", "https://a.com", "Snippet A", "Wikipedia", "surface")],
        taxonomy_references={"easy": ["Book A"], "mid": ["Paper B"], "deep": ["Thesis C"], "niche": ["Blog D"]},
    )
    ctx = bundle.to_context_string()
    assert "Test Topic" in ctx
    assert "Raft leader election" in ctx
    assert "Day 3" in ctx
    assert "Title A" in ctx
    assert "Book A" in ctx
