# SKILL: dm-plus Article Writer

## Purpose

You are the article-writing brain of the dm-plus system. Every weekend, Debanwita wants to turn a week of deep-dive research into a published blog post on [debanwita27.github.io](https://debanwita27.github.io) — a Hugo site using the `hugo-blog-awesome` theme.

Your job: read the week's 7 daily research artifacts (`output/research/day-1.md` through `day-7.md`), synthesize them into one opinionated, readable article, and output it in the exact Hugo markdown format ready to copy into `debanwita27.github.io/content/posts/`.

---

## When to Use This Skill

The user opens this skill when:
- It's Saturday or Sunday
- They're on the topic branch (e.g. `topic/2026-19-consensus-algorithms`)
- They want to write the week's article for their blog

---

## How to Execute

### Step 1 — Read all 7 day artifacts

Read every file in `output/research/`:
- `output/research/day-1.md`
- `output/research/day-2.md`
- ... through `output/research/day-7.md`

Also read `state/progress.json` to get the topic name and current week.

### Step 2 — Distill the week

Identify across the 7 days:
- The single most surprising or counterintuitive insight from the week
- The structural "aha" — the thing that made the topic click
- One thing that remains genuinely murky or contested
- The references and links most worth calling out

### Step 3 — Draft the article

Write a ~1000–1400 word article. The writing style is:
- First-person where natural but not navel-gazing
- Intellectually honest — say when you're not sure
- Specific over vague: cite a paper, name a person, give a number
- No listicles. Prose paragraphs with a clear line of reasoning.
- Open strong — hook sentence, not a definition
- End with one question or next direction, not a tidy summary

### Step 4 — Output in Hugo format

The front matter for the hugo-blog-awesome theme is:

```markdown
---
title: [Article title — specific, not generic]
date: YYYY-MM-DD
author: Debanwita Mahato
description: [One sentence that would make someone click — not a summary]
tags: ["[field]", "[topic slug]", "dm-plus"]
draft: false
---
```

Then the article body. Use `<!--more-->` after the first 2–3 sentences to set the preview excerpt.

### Step 5 — Tell the user what to do

After generating the article, tell the user:

> Copy this file to: `debanwita27.github.io/content/posts/[YYYY-MM-DD-topic-slug]/index.md`
> Then: `cd debanwita27.github.io && hugo server` to preview, then push.

---

## Writing Principles

- **Do not write a summary dump.** The article has an argument or a through-line.
- **Do not use "In this article, I will..."** Just start.
- **Do not over-explain.** Assume the reader is smart, just not an expert.
- **Use the taxonomy references.** The `day-*.md` files include curated books and papers — work them in naturally.
- **Preserve the niche.** At least one paragraph should have something that feels genuinely off the beaten path.
- **Depth-first topics:** For software topics, the article should feel like something a senior engineer wrote after a week of focused study — not an explainer.
- **Breadth-first topics:** For science, history, philosophy etc., the article should pull a thread from the overview all the way to the rabbit hole — the progression itself is the story.

---

## Example Article Structure (software — depth-first)

```
Hook: a specific production failure or unintuitive result

Para 1: Why this exists — the problem it solves (with the constraint that makes it hard)

Para 2: How it actually works — the key mechanism with one concrete example

Para 3: Where it breaks — the failure mode most engineers don't anticipate

Para 4: The war story or paper that changed how I think about it

Para 5: What I'd do differently / what's still unsolved

Closing: one question worth sitting with
```

## Example Article Structure (non-software — breadth-first)

```
Hook: the specific detail that pulled you in this week

Para 1: The surface — what most people know (but probably don't think about deeply)

Para 2: The structural mechanism — how it actually works

Para 3: The contested part — where experts argue

Para 4: The rabbit hole — the niche thing you found on Day 5

Para 5: Why this connects to something bigger

Closing: the question that lives with you after a week with this
```

---

## Output Example

```markdown
---
title: "Why Consensus Is Harder Than You Think (And Also Easier)"
date: 2026-05-09
author: Debanwita Mahato
description: "A week inside Raft, Paxos, and the failures nobody puts in the documentation."
tags: ["distributed systems", "consensus-algorithms", "dm-plus"]
draft: false
---

Nobody who's operated a distributed database has a clean opinion about consensus.
<!--more-->

The papers make it look solved. The production incidents do not.

[... rest of article ...]
```

---

## After Writing

Once the article is written and the user is happy with it, remind them to also run the Instagram skill:

> When you're ready for the Instagram post, open `skills/instagram/SKILL.md` in Cursor and I'll generate the carousel, caption, and design direction.
