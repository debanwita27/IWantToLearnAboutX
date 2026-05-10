"""
test_taxonomy.py — structural integrity tests for topics/taxonomy.json

Ensures the taxonomy is internally consistent so the researcher and
synthesizer never get a bad topic object at runtime.
"""

import json
import os
import pytest

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
TAXONOMY_PATH = os.path.join(REPO_ROOT, "topics", "taxonomy.json")
STATE_PATH = os.path.join(REPO_ROOT, "state", "progress.json")

VALID_DEPTH_MODES = {"depth_first", "breadth_first"}
VALID_REFERENCE_LEVELS = {"easy", "mid", "deep", "niche"}


@pytest.fixture(scope="module")
def taxonomy():
    with open(TAXONOMY_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def all_topics(taxonomy):
    """Flat list of all topic dicts with their field depth_mode injected."""
    topics = []
    for field in taxonomy["fields"]:
        for subfield in field.get("subfields", []):
            for topic in subfield.get("topics", []):
                topic = dict(topic)
                topic["_field_id"] = field["id"]
                topic["_depth_mode"] = field["depth_mode"]
                topics.append(topic)
    return topics


@pytest.fixture(scope="module")
def all_topic_ids(all_topics):
    return [t["id"] for t in all_topics]


@pytest.fixture(scope="module")
def state():
    with open(STATE_PATH) as f:
        return json.load(f)


# ── Schema ─────────────────────────────────────────────────────────────────────

def test_taxonomy_has_fields(taxonomy):
    assert "fields" in taxonomy
    assert len(taxonomy["fields"]) >= 10, "Expected at least 10 top-level fields"


def test_all_fields_have_depth_mode(taxonomy):
    for field in taxonomy["fields"]:
        assert "depth_mode" in field, f"Field '{field.get('id')}' missing depth_mode"
        assert field["depth_mode"] in VALID_DEPTH_MODES, (
            f"Field '{field['id']}' has invalid depth_mode '{field['depth_mode']}'"
        )


def test_software_field_is_depth_first(taxonomy):
    software = next((f for f in taxonomy["fields"] if f["id"] == "software"), None)
    assert software is not None, "software field not found"
    assert software["depth_mode"] == "depth_first"


def test_all_topics_have_required_fields(all_topics):
    required = {"id", "name", "subtopics", "niche_topics", "references"}
    for topic in all_topics:
        missing = required - set(topic.keys())
        assert not missing, f"Topic '{topic.get('id')}' missing fields: {missing}"


def test_all_topics_have_non_empty_subtopics(all_topics):
    for topic in all_topics:
        assert len(topic["subtopics"]) >= 2, (
            f"Topic '{topic['id']}' has fewer than 2 subtopics"
        )


def test_all_topics_have_non_empty_niche_topics(all_topics):
    for topic in all_topics:
        assert len(topic["niche_topics"]) >= 2, (
            f"Topic '{topic['id']}' has fewer than 2 niche_topics"
        )


def test_all_references_have_valid_levels(all_topics):
    for topic in all_topics:
        refs = topic.get("references", {})
        for level in refs:
            assert level in VALID_REFERENCE_LEVELS, (
                f"Topic '{topic['id']}' has unknown reference level '{level}'"
            )
        for level in VALID_REFERENCE_LEVELS:
            assert level in refs, f"Topic '{topic['id']}' missing reference level '{level}'"
            assert len(refs[level]) >= 1, (
                f"Topic '{topic['id']}' has empty '{level}' references"
            )


# ── Uniqueness ─────────────────────────────────────────────────────────────────

def test_no_duplicate_topic_ids(all_topic_ids):
    seen = set()
    dupes = []
    for tid in all_topic_ids:
        if tid in seen:
            dupes.append(tid)
        seen.add(tid)
    assert not dupes, f"Duplicate topic IDs found: {dupes}"


def test_no_duplicate_field_ids(taxonomy):
    ids = [f["id"] for f in taxonomy["fields"]]
    assert len(ids) == len(set(ids)), f"Duplicate field IDs: {[i for i in ids if ids.count(i) > 1]}"


# ── Queue ↔ Taxonomy consistency ───────────────────────────────────────────────

def test_all_queue_topics_exist_in_taxonomy(state, all_topic_ids):
    """Every topic in the queue must exist in taxonomy.json."""
    missing = [t for t in state["queue"] if t not in all_topic_ids]
    assert not missing, f"Queue topics not found in taxonomy: {missing}"


def test_current_topic_exists_in_taxonomy(state, all_topic_ids):
    current = state["current_topic_id"]
    assert current in all_topic_ids, (
        f"current_topic_id '{current}' not found in taxonomy"
    )


def test_completed_topics_exist_in_taxonomy(state, all_topic_ids):
    missing = [t for t in state["completed_topics"] if t not in all_topic_ids]
    assert not missing, f"Completed topics not in taxonomy: {missing}"


# ── Coverage ───────────────────────────────────────────────────────────────────

def test_taxonomy_has_minimum_topic_count(all_topics):
    assert len(all_topics) >= 30, f"Only {len(all_topics)} topics — expected 30+"


def test_taxonomy_covers_all_required_fields(taxonomy):
    field_ids = {f["id"] for f in taxonomy["fields"]}
    required = {
        "software", "science", "mathematics", "aerospace", "space_science",
        "biology", "marine_life", "machines", "weapons", "architecture",
        "world_politics", "history", "geography", "tech", "fashion",
        "consumerism", "marketing", "religion", "social_dynamics",
        "mythology", "theology", "philosophy", "brands", "poetry", "writing",
    }
    missing = required - field_ids
    assert not missing, f"Missing required fields in taxonomy: {missing}"
