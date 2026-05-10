"""
run.py — daily pipeline entry point for dm-plus

Called by the GitHub Action every morning at 3:35 AM UTC (9:05 AM IST).

Flow:
1. Read state/progress.json → active topic + subtopic + day
2. Research the specific subtopic for today's depth focus
3. Synthesize the digest via GitHub Models
4. Send email via Resend
5. Save artifact to output/research/day-N.md
6. Advance state (day counter, or rotate to next topic, or new subtopic pass)

Rotation model:
- All topics live in `rotation` (ordered list of topic IDs).
- Each week we study one topic's current subtopic.
- `rotation_pos` advances each week (round-robin).
- When rotation_pos wraps back to 0, every topic moves to its next subtopic.
- Topics that exhaust all subtopics + niche_topics are retired to completed_topics.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

from researcher import research, load_topic
from synthesizer import synthesize
from emailer import send, save_artifact

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "state", "progress.json")


def load_state() -> dict:
    with open(STATE_PATH) as f:
        return json.load(f)


def save_state(state: dict) -> None:
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)
    log.info("State saved.")


def current_iso_week() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.year}-{now.isocalendar()[1]:02d}"


def _subtopic_count(topic_id: str) -> int:
    """Total subtopics + niche_topics for a given topic (full rotation depth)."""
    try:
        topic = load_topic(topic_id)
        return len(topic.get("subtopics", [])) + len(topic.get("niche_topics", []))
    except ValueError:
        return 0


def advance_state(state: dict) -> dict:
    if state["current_day"] < 7:
        state["current_day"] += 1
        return state

    # Day 7 complete — move to next topic in rotation
    rotation = state["rotation"]
    rotation_pos = state["rotation_pos"]
    subtopic_progress = state["subtopic_progress"]

    next_pos = rotation_pos + 1

    if next_pos < len(rotation):
        state["rotation_pos"] = next_pos
    else:
        # Full pass complete — advance every topic to its next subtopic
        next_pos = 0
        exhausted = []
        for topic_id in list(rotation):
            subtopic_progress[topic_id] = subtopic_progress.get(topic_id, 0) + 1
            if subtopic_progress[topic_id] >= _subtopic_count(topic_id):
                exhausted.append(topic_id)

        for topic_id in exhausted:
            rotation.remove(topic_id)
            state["completed_topics"].append(topic_id)
            subtopic_progress.pop(topic_id, None)
            log.info(f"Topic '{topic_id}' fully exhausted — moved to completed.")

        if not rotation:
            log.warning("All topics fully completed! Add more to taxonomy.json.")

        state["rotation_pos"] = next_pos
        state["rotation"] = rotation
        state["subtopic_progress"] = subtopic_progress

    state["current_day"] = 1
    state["current_week"] = current_iso_week()
    return state


def main() -> None:
    state = load_state()
    rotation = state["rotation"]
    rotation_pos = state["rotation_pos"]
    topic_id = rotation[rotation_pos]
    subtopic_idx = state["subtopic_progress"].get(topic_id, 0)
    day = state["current_day"]
    week = state.get("current_week", current_iso_week())

    log.info(f"Starting daily run: topic={topic_id} subtopic_idx={subtopic_idx} day={day} week={week}")

    bundle = research(topic_id, day, subtopic_idx=subtopic_idx)
    log.info(f"Research complete: {len(bundle.articles)} articles collected")

    digest = synthesize(bundle, week)
    log.info("Synthesis complete")

    output_dir = os.path.join(os.path.dirname(__file__), "..", "output", "research")
    artifact_path = save_artifact(digest, output_dir=output_dir)
    log.info(f"Artifact written: {artifact_path}")

    send(digest)
    log.info("Email sent")

    state = advance_state(state)
    save_state(state)

    new_topic = state["rotation"][state["rotation_pos"]] if state["rotation"] else "none"
    log.info(f"State advanced: next_day={state['current_day']} next_topic={new_topic}")


if __name__ == "__main__":
    main()
