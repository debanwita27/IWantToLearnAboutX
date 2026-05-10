"""
synthesizer.py — LLM synthesis engine for dm-plus

Uses GitHub Models API (via GITHUB_TOKEN, zero extra cost) to synthesize
the daily research bundle into a structured digest.

GitHub Models endpoint: https://models.inference.ai.azure.com
Compatible with OpenAI SDK.
"""

import os
import json
import logging
from dataclasses import dataclass

from openai import OpenAI

from researcher import ResearchBundle

log = logging.getLogger(__name__)

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_MODELS_ENDPOINT = "https://models.inference.ai.azure.com"
MODEL = "gpt-4o-mini"


@dataclass
class DailyDigest:
    topic_id: str
    topic_name: str
    subtopic: str           # specific subtopic studied this week
    day: int
    week: str
    nugget: str             # main 600-900 word piece
    curated_links: list[dict]   # [{title, url, depth_tag, why}]
    reference_pick: str     # one Skunk Works-style recommendation
    progress_bar: str       # "Day 4/7 · Consensus Algorithms › Raft leader election"
    raw_bundle_context: str


BREADTH_SYSTEM = """You are a deeply curious researcher and gifted explainer — the kind of writer who makes
complex topics feel alive without dumbing them down. You have encyclopedic range but write with
specificity and wit. You hate vague summaries. You love the buried detail, the counterintuitive fact,
the structural insight that changes how someone sees something."""

DEPTH_SYSTEM = """You are a senior engineer with deep production experience and academic grounding.
You have read the papers, traced the source code, debugged the edge cases at 2 AM, and written
the post-mortems. You write for engineers who already know the surface and want the real stuff:
tradeoffs, war stories, the decisions that weren't obvious, the papers nobody reads but should."""


BREADTH_PROMPTS = {
    1: """Write Day 1 of a 7-day deep dive on: {topic_name}

DAY 1 FOCUS: Accessible overview — what is this, why does it matter, and what would change if it disappeared?

Requirements:
- Open with something surprising, counterintuitive, or viscerally interesting about this topic
- Give a genuine overview (not a Wikipedia intro) — include at least 2 things most people don't know
- 600–900 words, written with intellectual energy, not textbook flatness
- End with one question that Day 2 will answer

Research context:
{context}""",

    2: """Write Day 2 of a 7-day deep dive on: {topic_name}

DAY 2 FOCUS: Historical roots — the origin story, key figures, and the decisions that shaped what it became.

Requirements:
- Find the human drama in the history (disputes, accidents, obsessions, wrong turns that turned right)
- At least one figure who deserves more credit than they get
- 600–900 words
- End with a thread that leads into the mechanics (Day 3)

Research context:
{context}""",

    3: """Write Day 3 of a 7-day deep dive on: {topic_name}

DAY 3 FOCUS: Core mechanics — how it actually works, at the level of understanding, not just description.

Requirements:
- Explain the mechanism, not just the name. Use analogies sparingly but precisely.
- Include at least one thing that's more elegant than expected AND one thing that's messier than expected
- 600–900 words
- Surface the first hint of where this gets complicated (Day 4 preview)

Research context:
{context}""",

    4: """Write Day 4 of a 7-day deep dive on: {topic_name}

DAY 4 FOCUS: Controversies, unsolved problems, and edge cases — where the field argues with itself.

Requirements:
- At least one genuine open question that experts disagree on
- One thing that everyone "knows" but that turns out to be contested
- 600–900 words

Research context:
{context}""",

    5: """Write Day 5 of a 7-day deep dive on: {topic_name}

DAY 5 FOCUS: The rabbit hole — the niche, strange, buried, or forgotten angle most people never reach.

Requirements:
- This is the weird stuff. Obscure experiments. Forgotten papers. The corner of Reddit where the real enthusiasts live.
- At least one thing that feels like a secret or a discovery
- 600–900 words

Research context:
{context}""",

    6: """Write Day 6 of a 7-day deep dive on: {topic_name}

DAY 6 FOCUS: Real-world applications and adjacent fields — where does this show up in the world, and what does it touch?

Requirements:
- Concrete examples, not abstract "it's used in many industries"
- At least one surprising adjacent field or unexpected application
- 600–900 words

Research context:
{context}""",

    7: """Write Day 7 of a 7-day deep dive on: {topic_name}

DAY 7 FOCUS: Synthesis — what you now know, how your model changed, and what to explore next.

Requirements:
- 3 things you now understand that you didn't a week ago (be specific, not vague)
- One honest "I don't fully understand this yet" — with a pointer toward what to read next
- 600–900 words
- This should feel like the end of a good conversation, not a conclusion paragraph

Research context:
{context}""",
}

DEPTH_PROMPTS = {
    1: """Write Day 1 of a 7-day engineering deep dive on: {topic_name}

DAY 1 FOCUS: Mental model — where does this fit in the stack, why does it exist, and what problem does it solve that nothing else could?

Requirements:
- No "what is X" intro. Assume the reader is an engineer who's used it but wants to think clearly about it.
- Build the mental model from first principles: constraints → design choices → tradeoffs
- 700–900 words
- End with the core tension that Day 2 (internals) will resolve

Research context:
{context}""",

    2: """Write Day 2 of a 7-day engineering deep dive on: {topic_name}

DAY 2 FOCUS: Internal mechanics — how is this actually implemented?

Requirements:
- Get concrete. Name the data structures, the algorithms, the key code paths.
- What does the happy path look like? What's the most important 100 lines of source code?
- 700–900 words

Research context:
{context}""",

    3: """Write Day 3 of a 7-day engineering deep dive on: {topic_name}

DAY 3 FOCUS: The hard problems — failure modes, edge cases, and tradeoffs that engineers hit at scale.

Requirements:
- Real failure modes. Not "it can fail" but "here's what actually breaks and why."
- At least one tradeoff that has no clean answer — just costs and benefits
- 700–900 words

Research context:
{context}""",

    4: """Write Day 4 of a 7-day engineering deep dive on: {topic_name}

DAY 4 FOCUS: Production war stories — what actually goes wrong in real systems.

Requirements:
- Draw from post-mortems, engineering blogs, war stories (cite sources if possible)
- The lesson from each story should be engineering-actionable, not abstract
- 700–900 words

Research context:
{context}""",

    5: """Write Day 5 of a 7-day engineering deep dive on: {topic_name}

DAY 5 FOCUS: Read the source — key repos, annotated source walkthroughs, internals that aren't in the docs.

Requirements:
- Point to specific files, functions, or commits worth reading
- What does the source tell you that the documentation hides?
- 700–900 words

Research context:
{context}""",

    6: """Write Day 6 of a 7-day engineering deep dive on: {topic_name}

DAY 6 FOCUS: Academic lineage — the papers that defined this, the ones most engineers skip, and the niche forks.

Requirements:
- The original paper and what it got right vs wrong
- At least one paper that changed the field that most engineers haven't read
- 700–900 words

Research context:
{context}""",

    7: """Write Day 7 of a 7-day engineering deep dive on: {topic_name}

DAY 7 FOCUS: Build your intuition — open problems, what you'd design differently, and where the field is going.

Requirements:
- What would you change about the design if you could do it again?
- One open problem that hasn't been solved and is actually interesting
- 700–900 words

Research context:
{context}""",
}


LINK_CURATION_PROMPT = """Given these research articles, select 4–5 of the most valuable ones for someone doing
a progressive deep dive on "{topic_name}" (Day {day}/7, focus: {focus}).

For each selected article, write:
1. A one-sentence "why this is worth reading" — be specific about what insight it offers
2. A depth tag: surface | mid | deep | rabbit_hole

Return as JSON array:
[
  {{
    "title": "...",
    "url": "...",
    "depth_tag": "...",
    "why": "..."
  }}
]

Articles to select from:
{articles_list}"""


REFERENCE_PICK_PROMPT = """For someone on Day {day}/7 of a deep dive into "{topic_name}", recommend ONE
specific book, paper, blog post, or resource — like how 'Skunk Works' by Ben Rich is the perfect
recommendation for stealth aircraft: accessible enough to read end to end, specific enough to be
genuinely illuminating.

The day's focus is: {focus}

Available references from our curated taxonomy:
{references}

Respond with:
- **[Title] — [Author/Source]**
- One paragraph (3–5 sentences) on exactly why this resource, for this topic, on this day.
"""


def get_client() -> OpenAI:
    return OpenAI(
        base_url=GITHUB_MODELS_ENDPOINT,
        api_key=GITHUB_TOKEN,
    )


def _chat(client: OpenAI, system: str, user: str, max_tokens: int = 1500) -> str:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens,
        temperature=0.7,
    )
    return resp.choices[0].message.content.strip()


def synthesize(bundle: ResearchBundle, week: str) -> DailyDigest:
    client = get_client()
    day = bundle.day
    depth_mode = bundle.depth_mode

    system_prompt = DEPTH_SYSTEM if depth_mode == "depth_first" else BREADTH_SYSTEM
    prompts = DEPTH_PROMPTS if depth_mode == "depth_first" else BREADTH_PROMPTS
    subtopic_prefix = (
        f"**This week's specific focus: {bundle.subtopic}** "
        f"(within the broader topic of {bundle.topic_name})\n\n"
    )
    user_prompt = subtopic_prefix + prompts[day].format(
        topic_name=bundle.topic_name,
        context=bundle.to_context_string()[:3500],
    )

    log.info(f"Synthesizing nugget for Day {day} ({bundle.depth_mode})...")
    nugget = _chat(client, system_prompt, user_prompt, max_tokens=1200)

    articles_list = "\n".join(
        f"[{i+1}] {a.title} ({a.source})\nURL: {a.url}\nSnippet: {a.snippet[:200]}"
        for i, a in enumerate(bundle.articles[:15])
    )
    link_prompt = LINK_CURATION_PROMPT.format(
        topic_name=bundle.topic_name,
        day=day,
        focus=bundle.day_focus,
        articles_list=articles_list,
    )
    log.info("Curating links...")
    links_raw = _chat(client, "You are a precise research curator. Return only valid JSON.", link_prompt, max_tokens=600)
    try:
        json_match = links_raw[links_raw.find("["):links_raw.rfind("]") + 1]
        curated_links = json.loads(json_match)
    except Exception:
        curated_links = [
            {"title": a.title, "url": a.url, "depth_tag": a.depth_tag, "why": ""}
            for a in bundle.articles[:4]
        ]

    refs_text = "\n".join(
        f"{level}: {', '.join(refs)}"
        for level, refs in bundle.taxonomy_references.items()
    )
    ref_prompt = REFERENCE_PICK_PROMPT.format(
        day=day,
        topic_name=bundle.topic_name,
        focus=bundle.day_focus,
        references=refs_text,
    )
    log.info("Picking reference...")
    reference_pick = _chat(client, system_prompt, ref_prompt, max_tokens=300)

    progress_bar = (
        f"Day {day}/7 · {bundle.topic_name} › {bundle.subtopic} · "
        f"{bundle.depth_mode.replace('_', '-')}"
    )

    return DailyDigest(
        topic_id=bundle.topic_id,
        topic_name=bundle.topic_name,
        subtopic=bundle.subtopic,
        day=day,
        week=week,
        nugget=nugget,
        curated_links=curated_links,
        reference_pick=reference_pick,
        progress_bar=progress_bar,
        raw_bundle_context=bundle.to_context_string(),
    )
