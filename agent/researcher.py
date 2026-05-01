"""
researcher.py — multi-source knowledge fetcher for dm-plus

Queries arXiv, Semantic Scholar, CORE, Reddit, HackerNews, YouTube,
Wikipedia, Substack/Medium RSS, Internet Archive, and niche blogs.
Returns a structured ResearchBundle used by synthesizer.py.
"""

import os
import json
import time
import logging
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Optional
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup
import feedparser

try:
    import praw
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from googleapiclient.discovery import build as yt_build
    YT_AVAILABLE = True
except ImportError:
    YT_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "dm-plus/1.0 (IWantToLearnAboutX; educational research bot)"
}
TIMEOUT = 15


@dataclass
class Article:
    title: str
    url: str
    snippet: str
    source: str
    depth_tag: str  # surface | mid | deep | rabbit_hole


@dataclass
class ResearchBundle:
    topic_id: str
    topic_name: str
    day: int
    depth_mode: str           # depth_first | breadth_first
    day_focus: str            # human-readable focus for today
    articles: list[Article] = field(default_factory=list)
    taxonomy_references: dict = field(default_factory=dict)

    def to_context_string(self) -> str:
        lines = [
            f"# Research Bundle: {self.topic_name}",
            f"Day {self.day}/7 | Focus: {self.day_focus} | Mode: {self.depth_mode}",
            "",
        ]
        for i, a in enumerate(self.articles, 1):
            lines.append(f"## [{i}] [{a.depth_tag.upper()}] {a.title}")
            lines.append(f"Source: {a.source} | URL: {a.url}")
            lines.append(a.snippet.strip())
            lines.append("")
        if self.taxonomy_references:
            lines.append("## Curated References from Taxonomy")
            for level, refs in self.taxonomy_references.items():
                lines.append(f"**{level.capitalize()}**: {', '.join(refs)}")
        return "\n".join(lines)


def load_topic(topic_id: str) -> dict:
    taxonomy_path = os.path.join(
        os.path.dirname(__file__), "..", "topics", "taxonomy.json"
    )
    with open(taxonomy_path) as f:
        taxonomy = json.load(f)

    for field_node in taxonomy["fields"]:
        for subfield in field_node.get("subfields", []):
            for topic in subfield.get("topics", []):
                if topic["id"] == topic_id:
                    topic["_depth_mode"] = field_node["depth_mode"]
                    return topic
    raise ValueError(f"Topic '{topic_id}' not found in taxonomy")


def get_day_focus(day: int, depth_mode: str) -> str:
    breadth_arcs = {
        1: "Accessible overview — what is this and why does it matter",
        2: "Historical roots and key figures",
        3: "Core mechanics — how it actually works",
        4: "Controversies, unsolved problems, edge cases",
        5: "Niche rabbit hole — the weird, buried, obscure angle",
        6: "Real-world applications and adjacent fields",
        7: "Synthesis — what you now know and what to explore next",
    }
    depth_arcs = {
        1: "Mental model — where this fits in the stack and why it exists",
        2: "Internal mechanics — how it is actually implemented",
        3: "Hard problems — failure modes, edge cases, tradeoffs at scale",
        4: "Production war stories — what actually goes wrong in real systems",
        5: "Source code walkthroughs — key repos and annotated internals",
        6: "Academic lineage — seminal papers and the niche forks",
        7: "Build intuition — open problems and what you'd design differently",
    }
    arcs = depth_arcs if depth_mode == "depth_first" else breadth_arcs
    return arcs.get(day, breadth_arcs[1])


def build_search_queries(topic: dict, day: int, depth_mode: str) -> list[str]:
    name = topic["name"]
    subtopics = topic.get("subtopics", [])
    niche = topic.get("niche_topics", [])

    base = [name]
    if day <= 3:
        base += subtopics[:3]
    elif day == 4:
        base += [f"{name} failure modes", f"{name} production problems"]
    elif day == 5:
        base += niche[:3]
    elif day == 6:
        base += [f"{name} applications", f"{name} real world"]
    elif day == 7:
        base += [f"{name} open problems", f"{name} future research"]
    return base[:4]


# ── arXiv ─────────────────────────────────────────────────────────────────────

def fetch_arxiv(query: str, max_results: int = 5) -> list[Article]:
    url = "https://export.arxiv.org/api/query"
    params = {
        "search_query": f"all:{urllib.parse.quote(query)}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        root = ET.fromstring(r.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        articles = []
        for entry in root.findall("atom:entry", ns):
            title = entry.findtext("atom:title", "", ns).strip().replace("\n", " ")
            summary = entry.findtext("atom:summary", "", ns).strip().replace("\n", " ")
            link = entry.findtext("atom:id", "", ns).strip()
            articles.append(Article(
                title=title,
                url=link,
                snippet=summary[:500],
                source="arXiv",
                depth_tag="deep",
            ))
        return articles
    except Exception as e:
        log.warning(f"arXiv fetch failed for '{query}': {e}")
        return []


# ── Semantic Scholar ───────────────────────────────────────────────────────────

def fetch_semantic_scholar(query: str, max_results: int = 4) -> list[Article]:
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query,
        "limit": max_results,
        "fields": "title,abstract,url,year",
    }
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        articles = []
        for paper in data.get("data", []):
            abstract = (paper.get("abstract") or "")[:500]
            articles.append(Article(
                title=paper.get("title", ""),
                url=paper.get("url") or f"https://www.semanticscholar.org/paper/{paper.get('paperId','')}",
                snippet=abstract,
                source="Semantic Scholar",
                depth_tag="deep",
            ))
        return articles
    except Exception as e:
        log.warning(f"Semantic Scholar fetch failed for '{query}': {e}")
        return []


# ── CORE Open Access ───────────────────────────────────────────────────────────

def fetch_core(query: str, max_results: int = 3) -> list[Article]:
    url = "https://api.core.ac.uk/v3/search/works"
    params = {"q": query, "limit": max_results}
    api_key = os.environ.get("CORE_API_KEY")
    headers = {**HEADERS}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        r = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        articles = []
        for item in data.get("results", []):
            articles.append(Article(
                title=item.get("title", ""),
                url=item.get("downloadUrl") or item.get("sourceFulltextUrls", [""])[0],
                snippet=(item.get("abstract") or "")[:400],
                source="CORE",
                depth_tag="deep",
            ))
        return articles
    except Exception as e:
        log.warning(f"CORE fetch failed for '{query}': {e}")
        return []


# ── Reddit ─────────────────────────────────────────────────────────────────────

SUBREDDIT_MAP = {
    "software": ["programming", "softwaredevelopment", "compsci", "systems", "cscareerquestions"],
    "distributed_systems": ["programming", "distributed", "devops"],
    "science": ["askscience", "science", "physics", "biology", "chemistry"],
    "history": ["history", "AskHistorians", "HistoryMemes"],
    "philosophy": ["philosophy", "askphilosophy"],
    "default": ["askscience", "history", "philosophy", "worldnews", "programming", "books"],
}


def _get_subreddits(topic: dict, field_id: str) -> list[str]:
    subs = SUBREDDIT_MAP.get(field_id, SUBREDDIT_MAP["default"])
    return subs[:3]


def fetch_reddit(query: str, subreddits: list[str], max_posts: int = 4) -> list[Article]:
    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
    if not PRAW_AVAILABLE or not client_id or not client_secret:
        return _fetch_reddit_json(query, subreddits, max_posts)

    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent="dm-plus:v1.0",
        )
        articles = []
        for sub in subreddits:
            results = reddit.subreddit(sub).search(query, limit=2, sort="relevance")
            for post in results:
                body = (post.selftext or "")[:400]
                articles.append(Article(
                    title=post.title,
                    url=f"https://reddit.com{post.permalink}",
                    snippet=body,
                    source=f"Reddit r/{sub}",
                    depth_tag="mid",
                ))
        return articles[:max_posts]
    except Exception as e:
        log.warning(f"Reddit PRAW fetch failed: {e}")
        return _fetch_reddit_json(query, subreddits, max_posts)


def _fetch_reddit_json(query: str, subreddits: list[str], max_posts: int) -> list[Article]:
    articles = []
    for sub in subreddits[:2]:
        url = f"https://www.reddit.com/r/{sub}/search.json"
        params = {"q": query, "limit": 2, "sort": "relevance", "restrict_sr": 1}
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
            for post in r.json().get("data", {}).get("children", []):
                d = post["data"]
                articles.append(Article(
                    title=d.get("title", ""),
                    url=f"https://reddit.com{d.get('permalink','')}",
                    snippet=(d.get("selftext") or "")[:400],
                    source=f"Reddit r/{sub}",
                    depth_tag="mid",
                ))
        except Exception as e:
            log.warning(f"Reddit JSON fetch failed for r/{sub}: {e}")
    return articles[:max_posts]


# ── HackerNews ────────────────────────────────────────────────────────────────

def fetch_hackernews(query: str, max_results: int = 4) -> list[Article]:
    url = "https://hn.algolia.com/api/v1/search"
    params = {"query": query, "tags": "story", "hitsPerPage": max_results}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        articles = []
        for hit in r.json().get("hits", []):
            articles.append(Article(
                title=hit.get("title", ""),
                url=hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                snippet=(hit.get("story_text") or "")[:400],
                source="HackerNews",
                depth_tag="mid",
            ))
        return articles
    except Exception as e:
        log.warning(f"HackerNews fetch failed for '{query}': {e}")
        return []


# ── YouTube ────────────────────────────────────────────────────────────────────

def fetch_youtube_transcripts(query: str, max_videos: int = 2) -> list[Article]:
    yt_key = os.environ.get("YOUTUBE_API_KEY")
    if not YT_AVAILABLE or not yt_key:
        return []
    try:
        service = yt_build("youtube", "v3", developerKey=yt_key)
        search_resp = service.search().list(
            q=query, part="snippet", type="video", maxResults=max_videos,
            relevanceLanguage="en",
        ).execute()
        articles = []
        for item in search_resp.get("items", []):
            vid_id = item["id"]["videoId"]
            title = item["snippet"]["title"]
            description = item["snippet"].get("description", "")
            transcript_text = ""
            try:
                transcript = YouTubeTranscriptApi.get_transcript(vid_id)
                transcript_text = " ".join(t["text"] for t in transcript[:60])
            except Exception:
                transcript_text = description[:400]
            articles.append(Article(
                title=title,
                url=f"https://www.youtube.com/watch?v={vid_id}",
                snippet=transcript_text[:500],
                source="YouTube",
                depth_tag="surface",
            ))
        return articles
    except Exception as e:
        log.warning(f"YouTube fetch failed for '{query}': {e}")
        return []


# ── Wikipedia ─────────────────────────────────────────────────────────────────

def fetch_wikipedia(query: str) -> list[Article]:
    url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(
        query.replace(" ", "_")
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        extract = data.get("extract", "")[:600]
        return [Article(
            title=data.get("title", query),
            url=data.get("content_urls", {}).get("desktop", {}).get("page", ""),
            snippet=extract,
            source="Wikipedia",
            depth_tag="surface",
        )]
    except Exception as e:
        log.warning(f"Wikipedia fetch failed for '{query}': {e}")
        return []


# ── Substack / Medium RSS ─────────────────────────────────────────────────────

NICHE_FEEDS = [
    "https://substack.com/search/{query}?utm_source=global-search&searching=all_posts",
    "https://medium.com/search?q={query}",
]

CURATED_FEEDS = {
    "software": [
        "https://blog.pragmaticengineer.com/rss",
        "https://martinfowler.com/feed.atom",
        "https://brooker.co.za/blog/rss.xml",
    ],
    "science": [
        "https://www.quantamagazine.org/feed/",
    ],
    "philosophy": [
        "https://philosophybites.libsyn.com/rss",
    ],
    "history": [
        "https://www.lrb.co.uk/feeds/articles",
    ],
    "default": [
        "https://www.quantamagazine.org/feed/",
        "https://aeon.co/feed.rss",
    ],
}


def fetch_rss_feeds(query: str, field_id: str, max_items: int = 4) -> list[Article]:
    feeds = CURATED_FEEDS.get(field_id, CURATED_FEEDS["default"])
    articles = []
    query_lower = query.lower()
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:15]:
                title = entry.get("title", "")
                summary = BeautifulSoup(
                    entry.get("summary", entry.get("description", "")), "html.parser"
                ).get_text()[:400]
                link = entry.get("link", "")
                if query_lower in title.lower() or query_lower in summary.lower():
                    articles.append(Article(
                        title=title,
                        url=link,
                        snippet=summary,
                        source=f"RSS ({urllib.parse.urlparse(feed_url).netloc})",
                        depth_tag="mid",
                    ))
            if len(articles) >= max_items:
                break
        except Exception as e:
            log.warning(f"RSS feed failed {feed_url}: {e}")
    return articles[:max_items]


# ── Internet Archive ───────────────────────────────────────────────────────────

def fetch_internet_archive(query: str, max_results: int = 2) -> list[Article]:
    url = "https://archive.org/advancedsearch.php"
    params = {
        "q": query,
        "fl[]": "identifier,title,description",
        "rows": max_results,
        "output": "json",
        "mediatype": "texts",
    }
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        docs = r.json().get("response", {}).get("docs", [])
        articles = []
        for doc in docs:
            articles.append(Article(
                title=doc.get("title", ""),
                url=f"https://archive.org/details/{doc.get('identifier','')}",
                snippet=(doc.get("description") or "")[:400],
                source="Internet Archive",
                depth_tag="rabbit_hole",
            ))
        return articles
    except Exception as e:
        log.warning(f"Internet Archive fetch failed for '{query}': {e}")
        return []


# ── Niche Blog Scraper ─────────────────────────────────────────────────────────

NICHE_BLOG_MAP = {
    "consensus_algorithms": [
        "https://raft.github.io/",
        "https://brooker.co.za/blog/",
    ],
    "storage_engines": [
        "https://rocksdb.org/blog/",
        "https://www.scylladb.com/blog/",
    ],
    "ebpf": [
        "https://www.brendangregg.com/blog/",
        "https://cilium.io/blog/",
    ],
    "quantum_mechanics": [
        "https://scottaaronson.blog/",
    ],
    "bioluminescence": [
        "https://www.mbari.org/research/deep-sea/",
    ],
}


def fetch_niche_blogs(topic_id: str, query: str) -> list[Article]:
    urls = NICHE_BLOG_MAP.get(topic_id, [])
    articles = []
    for url in urls[:2]:
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            links = soup.find_all("a", href=True)
            query_words = set(query.lower().split())
            for link in links[:60]:
                href = link["href"]
                text = link.get_text(strip=True)
                if any(w in text.lower() for w in query_words) and len(text) > 10:
                    full_url = href if href.startswith("http") else urllib.parse.urljoin(url, href)
                    articles.append(Article(
                        title=text[:100],
                        url=full_url,
                        snippet=f"From {urllib.parse.urlparse(url).netloc}",
                        source=f"Blog ({urllib.parse.urlparse(url).netloc})",
                        depth_tag="rabbit_hole",
                    ))
                    break
        except Exception as e:
            log.warning(f"Niche blog fetch failed {url}: {e}")
    return articles


# ── Main orchestrator ──────────────────────────────────────────────────────────

def research(topic_id: str, day: int) -> ResearchBundle:
    topic = load_topic(topic_id)
    depth_mode = topic["_depth_mode"]
    day_focus = get_day_focus(day, depth_mode)
    queries = build_search_queries(topic, day, depth_mode)
    primary_query = queries[0]

    field_id = topic_id.split("_")[0] if "_" in topic_id else "default"

    bundle = ResearchBundle(
        topic_id=topic_id,
        topic_name=topic["name"],
        day=day,
        depth_mode=depth_mode,
        day_focus=day_focus,
        taxonomy_references=topic.get("references", {}),
    )

    log.info(f"Researching '{topic['name']}' — Day {day} ({day_focus})")
    log.info(f"Queries: {queries}")

    articles: list[Article] = []

    articles += fetch_wikipedia(primary_query)
    time.sleep(0.5)

    articles += fetch_hackernews(primary_query, max_results=3)
    time.sleep(0.5)

    for q in queries[:2]:
        articles += fetch_arxiv(q, max_results=3)
        time.sleep(1)

    articles += fetch_semantic_scholar(primary_query, max_results=3)
    time.sleep(0.5)

    if day >= 4:
        articles += fetch_core(primary_query, max_results=2)
        time.sleep(0.5)

    articles += fetch_reddit(
        primary_query,
        subreddits=SUBREDDIT_MAP.get(field_id, SUBREDDIT_MAP["default"]),
        max_posts=3,
    )
    time.sleep(0.5)

    articles += fetch_rss_feeds(primary_query, field_id, max_items=3)
    time.sleep(0.5)

    articles += fetch_youtube_transcripts(primary_query, max_videos=2)
    time.sleep(0.5)

    if day == 5 or day == 6:
        articles += fetch_internet_archive(primary_query, max_results=2)
        articles += fetch_niche_blogs(topic_id, primary_query)

    seen_urls = set()
    unique: list[Article] = []
    for a in articles:
        if a.url not in seen_urls and a.url:
            seen_urls.add(a.url)
            unique.append(a)

    bundle.articles = unique[:20]
    log.info(f"Collected {len(bundle.articles)} unique articles")
    return bundle


if __name__ == "__main__":
    import sys
    topic_id = sys.argv[1] if len(sys.argv) > 1 else "consensus_algorithms"
    day = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    bundle = research(topic_id, day)
    print(bundle.to_context_string())
