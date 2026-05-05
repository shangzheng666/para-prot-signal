from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "research-config.json"
OUTPUT_PATH = ROOT / "research-data.js"
NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
DEFAULT_EMAIL = "research-dashboard@example.com"


def request_json(url: str) -> dict:
  with urllib.request.urlopen(url, timeout=30) as response:
    return json.loads(response.read().decode("utf-8"))


def request_xml(url: str) -> ET.Element:
  with urllib.request.urlopen(url, timeout=45) as response:
    return ET.fromstring(response.read())


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


def search_topic(topic: dict, days: int, retmax: int, email: str, tool: str) -> list[str]:
  params = {
    "db": "pubmed",
    "term": topic["query"],
    "retmode": "json",
    "retmax": str(retmax),
    "sort": "pub+date",
    "datetype": "pdat",
    "reldate": str(days),
    "tool": tool,
    "email": email,
  }
  url = f"{NCBI_BASE}/esearch.fcgi?{urllib.parse.urlencode(params)}"
  data = request_json(url)
  return data.get("esearchresult", {}).get("idlist", [])


def fetch_articles(pmids: list[str], email: str, tool: str) -> ET.Element:
  params = {
    "db": "pubmed",
    "id": ",".join(pmids),
    "retmode": "xml",
    "tool": tool,
    "email": email,
  }
  url = f"{NCBI_BASE}/efetch.fcgi?{urllib.parse.urlencode(params)}"
  return request_xml(url)


def build_items(config: dict, email: str, tool: str) -> list[dict]:
  days = int(config.get("days", 7))
  retmax = int(config.get("retmax_per_topic", 25))
  now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
  items_by_pmid: dict[str, dict] = {}

  for topic in config.get("topics", []):
    tag = topic["tag"]
    pmids = search_topic(topic, days, retmax, email, tool)
    time.sleep(0.35)
    if not pmids:
      continue

    root = fetch_articles(pmids, email, tool)
    time.sleep(0.35)

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
        existing = items_by_pmid[pmid]
        if tag not in existing["topics"]:
          existing["topics"].append(tag)
          existing["tag"] = existing["topics"][0]
        existing["score"] = max(existing["score"], item["score"])
      else:
        items_by_pmid[pmid] = item

  return sorted(items_by_pmid.values(), key=lambda item: (item["ageHours"], -item["score"]))


def write_output(items: list[dict]) -> None:
  generated_at = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
  payload = json.dumps(items, ensure_ascii=False, indent=2)
  content = (
    f'window.researchLastUpdated = "{generated_at}";\n'
    f"window.researchItems = {payload};\n"
  )
  OUTPUT_PATH.write_text(content, encoding="utf-8")


def main() -> int:
  parser = argparse.ArgumentParser(description="Fetch recent PubMed articles for Parasite Signal.")
  parser.add_argument("--days", type=int, help="Override search window in days.")
  parser.add_argument("--email", default=DEFAULT_EMAIL, help="Email passed to NCBI E-utilities.")
  parser.add_argument("--tool", default="parasite-signal", help="Tool name passed to NCBI E-utilities.")
  args = parser.parse_args()

  config = load_config()
  if args.days:
    config["days"] = args.days

  items = build_items(config, args.email, args.tool)
  write_output(items)
  print(f"Wrote {len(items)} items to {OUTPUT_PATH}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
