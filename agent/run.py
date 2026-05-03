"""
run.py — daily pipeline entry point for dm-plus

Called by the GitHub Action every morning at 3:35 AM UTC (9:05 AM IST).

Flow:
1. Read state/progress.json → current topic + day
2. Research the topic for today's focus
3. Synthesize the digest via GitHub Models
4. Send email via Resend
5. Save artifact to output/research/day-N.md
6. Advance state (day counter or next topic)
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

from researcher import research
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


def advance_state(state: dict) -> dict:
    if state["current_day"] < 7:
        state["current_day"] += 1
    else:
        state["completed_topics"].append(state["current_topic_id"])
        queue = state.get("queue", [])
        if queue:
            state["current_topic_id"] = queue.pop(0)
            state["queue"] = queue
        else:
            log.warning("Topic queue is empty! Add more topics to taxonomy.json")
        state["current_day"] = 1
        state["current_week"] = current_iso_week()
    return state


def main() -> None:
    state = load_state()
    topic_id = state["current_topic_id"]
    day = state["current_day"]
    week = state.get("current_week", current_iso_week())

    log.info(f"Starting daily run: topic={topic_id} day={day} week={week}")

    bundle = research(topic_id, day)
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
    log.info(f"State advanced: next_day={state['current_day']} next_topic={state['current_topic_id']}")


if __name__ == "__main__":
    main()
