# IWantToLearnAboutX

> dm-plus: a plus version of myself, one week at a time.

A fully automated daily knowledge delivery system. Every week focuses on one topic. Every morning at 9:05 AM IST, an email lands with a progressive deep-dive — from mental models to production war stories, from surface overviews to rabbit holes buried in forgotten blogs and research papers.

At the end of each week, two Cursor skills help turn the week's research into a blog article (for [debanwita27.github.io](https://debanwita27.github.io)) and an Instagram carousel post.

---

## How It Works

```
Daily GitHub Action (9:05 AM IST)
  │
  ├── Read state/progress.json  →  current week + topic + day number
  ├── agent/researcher.py       →  fetch from arXiv, Reddit, HN, YouTube, Wikipedia,
  │                                Semantic Scholar, CORE, Substack RSS, niche blogs
  ├── agent/synthesizer.py      →  GitHub Models (GPT-4o mini) synthesizes daily digest
  │                                using depth-first arc (software) or breadth-first arc (all else)
  ├── agent/emailer.py          →  send HTML email via Resend
  ├── Commit research artifact  →  output/research/day-N.md on topic branch
  └── Update state/progress.json on main
```

**Weekend (manual):**
- Open `skills/article/SKILL.md` in Cursor → generates Hugo article draft
- Open `skills/instagram/SKILL.md` in Cursor → generates carousel copy + design direction

---

## Depth Modes

**Software topics** (distributed systems, OS internals, compilers, etc.) use a **depth-first arc**: Day 1 starts at internals, not "what is X". You already know the surface.

**Everything else** (physics, history, philosophy, fashion, marine biology, etc.) uses a **breadth-first arc**: Day 1 is the accessible overview, Day 5 is the rabbit hole.

---

## Weekly Branch Structure

- `main` — infrastructure, taxonomy, state
- `topic/YYYY-WW-<slug>` — one branch per week, holds all 7 daily research artifacts

```
topic/2026-19-consensus-algorithms/
  output/research/
    day-1.md  ←  Mental model + stack placement
    day-2.md  ←  Raft internals
    day-3.md  ←  Failure modes
    day-4.md  ←  Production war stories
    day-5.md  ←  Source code walkthroughs
    day-6.md  ←  Academic lineage (papers)
    day-7.md  ←  Synthesis + open problems
```

---

## Setup

### 1. Fork / clone this repo

### 2. Get your API keys (all free)

| Key | Where |
|-----|-------|
| `RESEND_API_KEY` | [resend.com](https://resend.com) — free, 3k emails/month |
| `EMAIL_TO` | Your email address |
| `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` | [reddit.com/prefs/apps](https://reddit.com/prefs/apps) |
| `YOUTUBE_API_KEY` | [Google Cloud Console](https://console.cloud.google.com) — free 10k units/day |

`GITHUB_TOKEN` is auto-provided by GitHub Actions — no setup needed. It's used for the LLM (GitHub Models).

### 3. Add secrets to your repo

`Settings → Secrets and variables → Actions → New repository secret`

### 4. That's it

The action runs every day at 3:35 AM UTC (9:05 AM IST). First run picks Week 1, Topic 1 from the queue.

---

## Topic Queue

~250+ topics seeded across 25 fields. Software topics come first and go deep immediately. Everything else starts with a surface sweep and spirals inward over multiple passes.

See [`topics/taxonomy.json`](topics/taxonomy.json) for the full tree.

---

## Cursor Skills

| Skill | File | When to use |
|-------|------|-------------|
| Article Writer | `skills/article/SKILL.md` | Saturday — turn the week into a blog post |
| Instagram Advisor | `skills/instagram/SKILL.md` | Weekend — generate carousel, caption, design direction |

---

## Project

**dm-plus** — be a better and more knowledgeable version of yourself than yesterday.
