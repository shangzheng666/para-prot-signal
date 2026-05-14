"""Fetch AI & semiconductor news from public RSS feeds.

Uses only Python standard library — no pip dependencies required.
Outputs tech-news-data.js and tech-news-data.md in the repo root.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JS = ROOT / "tech-news-data.js"
OUTPUT_MD = ROOT / "tech-news-data.md"

# ── RSS source registry ─────────────────────────────────────────────
RSS_SOURCES: list[dict[str, str]] = [
    # AI 研究
    {"name": "ArXiv cs.AI", "category": "AI 研究",
     "url": "https://rss.arxiv.org/rss/cs.AI"},
    {"name": "ArXiv cs.LG", "category": "AI 研究",
     "url": "https://rss.arxiv.org/rss/cs.LG"},
    # AI 产业
    {"name": "TechCrunch AI", "category": "AI 产业",
     "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
    {"name": "The Verge AI", "category": "AI 产业",
     "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"},
    {"name": "VentureBeat AI", "category": "AI 产业",
     "url": "https://venturebeat.com/category/ai/feed/"},
    # 半导体
    {"name": "SemiEngineering", "category": "半导体",
     "url": "https://semiengineering.com/feed/"},
    {"name": "EE Times", "category": "半导体",
     "url": "https://www.eetimes.com/feed/"},
    # 芯片/市场
    {"name": "Tom's Hardware", "category": "芯片/市场",
     "url": "https://www.tomshardware.com/feeds/all"},
    {"name": "Wccftech", "category": "芯片/市场",
     "url": "https://wccftech.com/feed/"},
    {"name": "VideoCardz", "category": "芯片/市场",
     "url": "https://videocardz.com/feed"},
]


# ── helpers ──────────────────────────────────────────────────────────

def _read_url(url: str, *, timeout: int = 30) -> bytes:
    """Fetch *url* with up to 3 attempts and exponential backoff."""
    max_attempts = 3
    backoff = 2
    req = urllib.request.Request(url, headers={
        "User-Agent": "TechNewsFetcher/1.0 (RSS reader; +https://github.com)",
    })
    for attempt in range(1, max_attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code < 500:
                raise
            if attempt == max_attempts:
                raise
            print(f"  [retry] HTTP {exc.code} attempt {attempt}/{max_attempts}",
                  file=sys.stderr)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if attempt == max_attempts:
                raise
            print(f"  [retry] {type(exc).__name__} attempt {attempt}/{max_attempts}",
                  file=sys.stderr)
        time.sleep(backoff)
        backoff *= 2
    raise RuntimeError("exhausted retries")


def clean(text: str | None) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)       # strip HTML tags
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ── date parsing ─────────────────────────────────────────────────────

_DATE_FORMATS = [
    "%a, %d %b %Y %H:%M:%S %z",   # RFC 822  (RSS 2.0)
    "%a, %d %b %Y %H:%M:%S %Z",
    "%Y-%m-%dT%H:%M:%S%z",        # ISO 8601 (Atom)
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
]


def parse_date(raw: str | None) -> dt.datetime | None:
    if not raw:
        return None
    raw = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(raw, fmt)
        except ValueError:
            continue
    # last resort: try to find YYYY-MM-DD in the string
    m = re.search(r"(\d{4}-\d{2}-\d{2})", raw)
    if m:
        try:
            return dt.datetime.strptime(m.group(1), "%Y-%m-%d")
        except ValueError:
            pass
    return None


def date_str(d: dt.datetime | None) -> str:
    if d is None:
        return ""
    return d.strftime("%Y-%m-%d")


# ── feed parsing (RSS 2.0 + Atom) ───────────────────────────────────

ATOM_NS = "{http://www.w3.org/2005/Atom}"


def _text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return clean("".join(el.itertext()))


def parse_feed(xml_bytes: bytes, source: dict[str, str]) -> list[dict]:
    """Parse RSS 2.0 or Atom feed, return list of item dicts."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []

    items: list[dict] = []

    # RSS 2.0: <rss><channel><item>…
    for item_el in root.iter("item"):
        title = _text(item_el.find("title"))
        link = _text(item_el.find("link"))
        desc = _text(item_el.find("description"))
        pub = _text(item_el.find("pubDate"))
        if not title:
            continue
        items.append({
            "title": title,
            "link": link,
            "description": desc[:500] if desc else "",
            "pub_date": date_str(parse_date(pub)),
            "source": source["name"],
            "category": source["category"],
        })

    # Atom: <feed><entry>…
    for entry in root.iter(f"{ATOM_NS}entry"):
        title = _text(entry.find(f"{ATOM_NS}title"))
        link_el = entry.find(f"{ATOM_NS}link")
        link = (link_el.attrib.get("href", "") if link_el is not None else "")
        summary = _text(entry.find(f"{ATOM_NS}summary"))
        if not summary:
            summary = _text(entry.find(f"{ATOM_NS}content"))
        updated = _text(entry.find(f"{ATOM_NS}updated"))
        if not updated:
            updated = _text(entry.find(f"{ATOM_NS}published"))
        if not title:
            continue
        items.append({
            "title": title,
            "link": link,
            "description": clean(summary)[:500] if summary else "",
            "pub_date": date_str(parse_date(updated)),
            "source": source["name"],
            "category": source["category"],
        })

    # Also handle Atom entries without namespace (some feeds)
    if not items:
        for entry in root.iter("entry"):
            title = _text(entry.find("title"))
            link_el = entry.find("link")
            link = (link_el.attrib.get("href", "") if link_el is not None else "")
            summary = _text(entry.find("summary"))
            if not summary:
                summary = _text(entry.find("content"))
            updated = _text(entry.find("updated"))
            if not updated:
                updated = _text(entry.find("published"))
            if not title:
                continue
            items.append({
                "title": title,
                "link": link,
                "description": clean(summary)[:500] if summary else "",
                "pub_date": date_str(parse_date(updated)),
                "source": source["name"],
                "category": source["category"],
            })

    return items


# ── RDF/RSS 1.0 fallback (ArXiv uses this) ──────────────────────────

RDF_NS = "{http://purl.org/rss/1.0/}"
DC_NS = "{http://purl.org/dc/elements/1.1/}"


def parse_rdf_feed(xml_bytes: bytes, source: dict[str, str]) -> list[dict]:
    """Parse RDF/RSS 1.0 feed (e.g. ArXiv)."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []

    items: list[dict] = []
    for item_el in root.iter(f"{RDF_NS}item"):
        title = _text(item_el.find(f"{RDF_NS}title"))
        link = _text(item_el.find(f"{RDF_NS}link"))
        desc = _text(item_el.find(f"{RDF_NS}description"))
        pub = _text(item_el.find(f"{DC_NS}date"))
        if not title:
            continue
        items.append({
            "title": title,
            "link": link,
            "description": clean(desc)[:500] if desc else "",
            "pub_date": date_str(parse_date(pub)),
            "source": source["name"],
            "category": source["category"],
        })
    return items


# ── main logic ───────────────────────────────────────────────────────

def fetch_all(days: int) -> list[dict]:
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    all_items: list[dict] = []
    seen_urls: set[str] = set()

    for source in RSS_SOURCES:
        print(f"Fetching {source['name']} ({source['category']})...",
              file=sys.stderr)
        try:
            raw = _read_url(source["url"])
        except Exception as exc:
            print(f"  SKIP: {exc}", file=sys.stderr)
            continue

        items = parse_feed(raw, source)
        if not items:
            items = parse_rdf_feed(raw, source)

        count = 0
        for item in items:
            url = item["link"]
            if not url or url in seen_urls:
                continue
            # filter by date if available
            if item["pub_date"]:
                try:
                    pub_dt = dt.datetime.strptime(item["pub_date"], "%Y-%m-%d")
                    pub_dt = pub_dt.replace(tzinfo=dt.timezone.utc)
                    if pub_dt < cutoff:
                        continue
                except ValueError:
                    pass
            seen_urls.add(url)
            all_items.append(item)
            count += 1
        print(f"  Got {count} articles", file=sys.stderr)
        time.sleep(0.5)  # be polite

    # sort by date descending, undated items last
    all_items.sort(key=lambda x: x["pub_date"] or "0000-00-00", reverse=True)
    return all_items


def write_js(items: list[dict]) -> None:
    generated_at = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    payload = json.dumps(items, ensure_ascii=False, indent=2)
    content = (
        f'window.techNewsLastUpdated = "{generated_at}";\n'
        f"window.techNewsItems = {payload};\n"
    )
    OUTPUT_JS.write_text(content, encoding="utf-8")


def write_md(items: list[dict]) -> None:
    generated_at = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")

    # category stats
    cat_counts: dict[str, int] = {}
    for item in items:
        cat_counts[item["category"]] = cat_counts.get(item["category"], 0) + 1

    # group by date
    by_date: dict[str, list[dict]] = {}
    for item in items:
        key = item["pub_date"] or "未知日期"
        by_date.setdefault(key, []).append(item)

    lines: list[str] = [
        f"# AI & 半导体资讯 — {generated_at}",
        "",
        "共 **{}** 篇文章（{}）".format(
            len(items),
            " · ".join(f"{c} {n}" for c, n in cat_counts.items()),
        ),
        "",
        "---",
        "",
    ]

    for date_key in sorted(by_date, reverse=True):
        date_items = by_date[date_key]
        lines.append(f"## {date_key}")
        lines.append("")
        lines.append("| # | 标题 | 来源 | 分类 |")
        lines.append("|---|------|------|------|")
        for i, item in enumerate(date_items, 1):
            title = item["title"].replace("|", "\\|")
            link = item["link"]
            title_cell = f"[{title}]({link})" if link else title
            lines.append(
                f"| {i} | {title_cell} | {item['source']} | {item['category']} |"
            )
        lines.append("")

    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch AI & semiconductor news from RSS feeds."
    )
    parser.add_argument(
        "--days", type=int, default=3,
        help="Only keep articles from the last N days (default: 3)."
    )
    args = parser.parse_args()

    items = fetch_all(args.days)
    write_js(items)
    write_md(items)
    print(f"Wrote {len(items)} items to {OUTPUT_JS}", file=sys.stderr)
    print(f"Wrote {len(items)} items to {OUTPUT_MD}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
