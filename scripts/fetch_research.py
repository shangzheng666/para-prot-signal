from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "research-config.json"
OUTPUT_PATH = ROOT / "research-data.js"
MD_OUTPUT_PATH = ROOT / "research-data.md"
NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
DEFAULT_EMAIL = "research-dashboard@example.com"


def _common_params(email: str, tool: str, api_key: str | None) -> dict[str, str]:
  """Return the shared NCBI E-utilities param dict."""
  params: dict[str, str] = {"db": "pubmed", "tool": tool, "email": email}
  if api_key:
    params["api_key"] = api_key
  return params


def _read_url(url: str, *, timeout: int = 30, decode: bool = True) -> str | bytes:
  """Fetch *url* with up to 3 attempts and exponential backoff.

  Retries on 5xx HTTPError, URLError, TimeoutError, and ConnectionError.
  Does NOT retry on 4xx (client errors).
  """
  max_attempts = 3
  backoff = 2
  for attempt in range(1, max_attempts + 1):
    try:
      with urllib.request.urlopen(url, timeout=timeout) as response:
        data = response.read()
        return data.decode("utf-8") if decode else data
    except urllib.error.HTTPError as exc:
      if exc.code < 500:
        raise  # 4xx — don't retry
      if attempt == max_attempts:
        raise
      print(f"[retry] HTTP {exc.code} on attempt {attempt}/{max_attempts}, "
            f"retrying in {backoff}s …", file=sys.stderr)
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
      if attempt == max_attempts:
        raise
      print(f"[retry] {type(exc).__name__} on attempt {attempt}/{max_attempts}, "
            f"retrying in {backoff}s …", file=sys.stderr)
    time.sleep(backoff)
    backoff *= 2
  # unreachable, but keeps the type checker happy
  raise RuntimeError("_read_url: exhausted retries")


def request_json(url: str) -> dict:
  return json.loads(_read_url(url, timeout=30, decode=True))


def request_xml(url: str) -> ET.Element:
  return ET.fromstring(_read_url(url, timeout=45, decode=False))


def load_config() -> dict:
  if CONFIG_PATH.exists():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

  return {
    "days": 7,
    "retmax_per_topic": 25,
    "topics": [
      {
        "tag": "Toxoplasma",
        "query": "(Toxoplasma gondii[Title/Abstract] OR toxoplasmosis[Title/Abstract])",
      },
      {
        "tag": "Plasmodium",
        "query": "(Plasmodium[Title/Abstract] OR Plasmodium falciparum[Title/Abstract])",
      },
    ],
  }


def clean_text(value: str | None) -> str:
  if not value:
    return ""
  text = html.unescape(value)
  text = re.sub(r"\s+", " ", text)
  return text.strip()


def element_text(element: ET.Element | None) -> str:
  if element is None:
    return ""
  return clean_text("".join(element.itertext()))


def parse_pub_date(article: ET.Element) -> str:
  article_date = article.find("./MedlineCitation/Article/ArticleDate")
  if article_date is not None:
    year = element_text(article_date.find("Year"))
    month = element_text(article_date.find("Month")).zfill(2)
    day = element_text(article_date.find("Day")).zfill(2)
    if year and month and day:
      return f"{year}-{month}-{day}"

  pub_date = article.find("./MedlineCitation/Article/Journal/JournalIssue/PubDate")
  if pub_date is None:
    return ""

  year = element_text(pub_date.find("Year"))
  month = element_text(pub_date.find("Month"))
  day = element_text(pub_date.find("Day"))
  medline = element_text(pub_date.find("MedlineDate"))

  month_map = {
    "Jan": "01",
    "Feb": "02",
    "Mar": "03",
    "Apr": "04",
    "May": "05",
    "Jun": "06",
    "Jul": "07",
    "Aug": "08",
    "Sep": "09",
    "Oct": "10",
    "Nov": "11",
    "Dec": "12",
  }

  if year:
    if month:
      month = month_map.get(month[:3], month.zfill(2) if month.isdigit() else "01")
      day = day.zfill(2) if day.isdigit() else "01"
      return f"{year}-{month}-{day}"
    return year

  return medline


def parse_date_for_age(pub_date: str, now: dt.datetime) -> float:
  for fmt, length in (("%Y-%m-%d", 10), ("%Y-%m", 7), ("%Y", 4)):
    try:
      parsed = dt.datetime.strptime(pub_date[:length], fmt)
      return max(0.0, (now - parsed).total_seconds() / 3600)
    except ValueError:
      continue
  return 9999.0


def parse_authors(article: ET.Element) -> list[str]:
  authors: list[str] = []
  for author in article.findall("./MedlineCitation/Article/AuthorList/Author"):
    collective = element_text(author.find("CollectiveName"))
    if collective:
      authors.append(collective)
      continue

    last = element_text(author.find("LastName"))
    initials = element_text(author.find("Initials"))
    if last:
      authors.append(f"{last} {initials}".strip())

  return authors[:6]


def parse_abstract(article: ET.Element) -> str:
  parts: list[str] = []
  for abstract_text in article.findall("./MedlineCitation/Article/Abstract/AbstractText"):
    label = abstract_text.attrib.get("Label")
    text = element_text(abstract_text)
    if not text:
      continue
    parts.append(f"{label}: {text}" if label else text)
  return clean_text(" ".join(parts))


def summarize_abstract(abstract: str, max_chars: int = 460) -> str:
  if not abstract:
    return "PubMed 暂无摘要。"
  if len(abstract) <= max_chars:
    return abstract
  return abstract[:max_chars].rsplit(" ", 1)[0].rstrip(".,;:") + "..."


def article_ids(article: ET.Element) -> tuple[str, str]:
  doi = ""
  for item in article.findall("./PubmedData/ArticleIdList/ArticleId"):
    if item.attrib.get("IdType") == "doi":
      doi = element_text(item)
      break
  pmid = element_text(article.find("./MedlineCitation/PMID"))
  return pmid, doi


def search_topic(
  topic: dict, days: int, retmax: int, email: str, tool: str, api_key: str | None
) -> list[str]:
  params = _common_params(email, tool, api_key)
  params.update({
    "term": topic["query"],
    "retmode": "json",
    "retmax": str(retmax),
    "sort": "pub+date",
    "datetype": "pdat",
    "reldate": str(days),
  })
  url = f"{NCBI_BASE}/esearch.fcgi?{urllib.parse.urlencode(params)}"
  data = request_json(url)
  return data.get("esearchresult", {}).get("idlist", [])


def fetch_articles(
  pmids: list[str], email: str, tool: str, api_key: str | None
) -> ET.Element:
  params = _common_params(email, tool, api_key)
  params.update({"id": ",".join(pmids), "retmode": "xml"})
  url = f"{NCBI_BASE}/efetch.fcgi?{urllib.parse.urlencode(params)}"
  return request_xml(url)


def _merge_duplicate(existing: dict, new_item: dict) -> None:
  """Merge *new_item* into *existing*: union topics, take max score, keep more recent pubDate."""
  for t in new_item["topics"]:
    if t not in existing["topics"]:
      existing["topics"].append(t)
  existing["tag"] = existing["topics"][0]
  existing["score"] = max(existing["score"], new_item["score"])
  if new_item["pubDate"] > existing["pubDate"]:
    existing["pubDate"] = new_item["pubDate"]
    existing["ageHours"] = new_item["ageHours"]


def build_items(config: dict, email: str, tool: str, api_key: str | None) -> list[dict]:
  days = int(config.get("days", 7))
  retmax = int(config.get("retmax_per_topic", 25))
  now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
  sleep_seconds = 0.11 if api_key else 0.35
  items_by_pmid: dict[str, dict] = {}

  for topic in config.get("topics", []):
    tag = topic["tag"]
    pmids = search_topic(topic, days, retmax, email, tool, api_key)
    time.sleep(sleep_seconds)
    if not pmids:
      continue

    root = fetch_articles(pmids, email, tool, api_key)
    time.sleep(sleep_seconds)

    for rank, article in enumerate(root.findall("./PubmedArticle")):
      pmid, doi = article_ids(article)
      if not pmid:
        continue

      title = element_text(article.find("./MedlineCitation/Article/ArticleTitle"))
      journal = element_text(article.find("./MedlineCitation/Article/Journal/Title"))
      pub_date = parse_pub_date(article)
      abstract = parse_abstract(article)
      authors = parse_authors(article)
      age_hours = parse_date_for_age(pub_date, now)
      item = {
        "id": f"pubmed-{pmid}",
        "title": title or f"PubMed {pmid}",
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "source": "PubMed",
        "tag": tag,
        "topics": [tag],
        "type": "PubMed",
        "editor": "NCBI",
        "ageHours": round(age_hours, 1),
        "score": max(1, 100 - rank * 2),
        "journal": journal,
        "pubDate": pub_date,
        "authors": authors,
        "pmid": pmid,
        "doi": doi,
        "why": summarize_abstract(abstract),
      }

      if pmid in items_by_pmid:
        _merge_duplicate(items_by_pmid[pmid], item)
      else:
        items_by_pmid[pmid] = item

  # DOI-based secondary deduplication.
  # bioRxiv preprints vs journal versions usually have different DOIs, so this
  # primarily catches same-article-different-PMID cases (e.g. ahead-of-print
  # vs final publication with distinct PMIDs but identical DOI).
  seen_doi: dict[str, str] = {}  # doi -> pmid
  for pmid, item in list(items_by_pmid.items()):
    doi = item.get("doi", "")
    if not doi:
      continue
    if doi in seen_doi:
      _merge_duplicate(items_by_pmid[seen_doi[doi]], item)
      del items_by_pmid[pmid]
    else:
      seen_doi[doi] = pmid

  return sorted(items_by_pmid.values(), key=lambda item: (item["ageHours"], -item["score"]))


def write_output(items: list[dict]) -> None:
  generated_at = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
  payload = json.dumps(items, ensure_ascii=False, indent=2)
  content = (
    f'window.researchLastUpdated = "{generated_at}";\n'
    f"window.researchItems = {payload};\n"
  )
  OUTPUT_PATH.write_text(content, encoding="utf-8")


def write_markdown(items: list[dict]) -> None:
  generated_at = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
  # Group items by pubDate
  by_date: dict[str, list[dict]] = {}
  for item in items:
    date_key = item.get("pubDate", "Unknown")[:10]
    by_date.setdefault(date_key, []).append(item)

  # Topic stats
  topic_counts: dict[str, int] = {}
  for item in items:
    for t in item.get("topics", []):
      topic_counts[t] = topic_counts.get(t, 0) + 1

  lines: list[str] = []
  lines.append(f"# PubMed Research Feed — {generated_at}")
  lines.append("")
  stats = " · ".join(f"{t} {c}" for t, c in topic_counts.items())
  lines.append(f"共 **{len(items)}** 篇文章（{stats}）")
  lines.append("")
  lines.append("---")
  lines.append("")

  for date_key in sorted(by_date, reverse=True):
    date_items = by_date[date_key]
    lines.append(f"## {date_key}")
    lines.append("")
    lines.append("| # | 标题 | 期刊 | 主题 | DOI |")
    lines.append("|---|------|------|------|-----|")
    for i, item in enumerate(date_items, 1):
      title = item.get("title", "").replace("|", "\\|")
      journal = item.get("journal", "").replace("|", "\\|")
      topics = " · ".join(item.get("topics", []))
      doi = item.get("doi", "")
      doi_link = f"[{doi}](https://doi.org/{doi})" if doi else "—"
      url = item.get("url", "")
      title_link = f"[{title}]({url})" if url else title
      lines.append(f"| {i} | {title_link} | {journal} | {topics} | {doi_link} |")
    lines.append("")

  MD_OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
  parser = argparse.ArgumentParser(description="Fetch recent PubMed articles for Parasite Signal.")
  parser.add_argument("--days", type=int, help="Override search window in days.")
  parser.add_argument("--email", default=DEFAULT_EMAIL, help="Email passed to NCBI E-utilities.")
  parser.add_argument("--tool", default="parasite-signal", help="Tool name passed to NCBI E-utilities.")
  parser.add_argument("--api-key", default=None, help="NCBI API key (or set NCBI_API_KEY env var).")
  args = parser.parse_args()

  api_key = args.api_key or os.environ.get("NCBI_API_KEY")
  if api_key:
    print("Using NCBI API key (10 req/s limit)", file=sys.stderr)
  else:
    print("Running anonymous, 3 req/s", file=sys.stderr)

  config = load_config()
  if args.days:
    config["days"] = args.days

  items = build_items(config, args.email, args.tool, api_key)
  write_output(items)
  write_markdown(items)
  print(f"Wrote {len(items)} items to {OUTPUT_PATH}")
  print(f"Wrote {len(items)} items to {MD_OUTPUT_PATH}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
