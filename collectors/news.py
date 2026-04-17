"""
news.py — NuCana 관련 뉴스 수집 (RSS 피드 우선, NewsAPI 선택)
"""

import requests
import os
import json
import re
from datetime import datetime, timezone
from xml.etree import ElementTree as ET


HEADERS = {"User-Agent": "NCNA-Analyzer research@example.com"}

# 무료 RSS 피드 목록
RSS_FEEDS = [
    # Google News RSS (NuCana 검색)
    "https://news.google.com/rss/search?q=NuCana+NCNA+stock&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=NuCana+Acelarin+clinical+trial&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=NUC-1031+NUC-3373+cancer&hl=en-US&gl=US&ceid=US:en",
    # SEC 뉴스릴리즈 RSS
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001709626&type=6-K&dateb=&owner=include&count=10&search_text=&output=atom",
]

POSITIVE_KEYWORDS = [
    "positive", "success", "approval", "breakthrough", "efficacy",
    "promising", "trial success", "partnership", "milestone", "granted",
    "favorable", "complete response", "remission",
]
NEGATIVE_KEYWORDS = [
    "failure", "failed", "halt", "discontinued", "reject", "setback",
    "dilution", "offering", "downgrade", "miss", "disappointing",
    "terminated", "adverse", "concern", "risk",
]


def collect() -> dict:
    result = {
        "updated_at": datetime.utcnow().isoformat(),
        "articles": [],
        "sentiment_summary": {},
    }

    seen_titles = set()

    # RSS 수집
    for feed_url in RSS_FEEDS:
        articles = _parse_rss(feed_url)
        for a in articles:
            title = a.get("title", "")
            if title and title not in seen_titles:
                seen_titles.add(title)
                a["sentiment"] = _score_sentiment(title + " " + a.get("summary", ""))
                result["articles"].append(a)

    # NewsAPI (키 있으면 추가 수집)
    news_api_key = os.getenv("NEWS_API_KEY")
    if news_api_key:
        newsapi_articles = _fetch_newsapi(news_api_key)
        for a in newsapi_articles:
            title = a.get("title", "")
            if title and title not in seen_titles:
                seen_titles.add(title)
                a["sentiment"] = _score_sentiment(title + " " + a.get("summary", ""))
                result["articles"].append(a)

    # 최신순 정렬
    result["articles"].sort(key=lambda x: x.get("published", ""), reverse=True)
    result["articles"] = result["articles"][:50]  # 최대 50건

    # 센티멘트 요약
    sentiments = [a["sentiment"] for a in result["articles"]]
    result["sentiment_summary"] = {
        "total": len(sentiments),
        "positive": sentiments.count("positive"),
        "negative": sentiments.count("negative"),
        "neutral": sentiments.count("neutral"),
        "score": _overall_score(sentiments),
    }

    return result


def _parse_rss(url: str) -> list:
    articles = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        root = ET.fromstring(r.content)

        # RSS 2.0
        for item in root.findall(".//item"):
            title = _text(item, "title")
            link = _text(item, "link")
            pub_date = _text(item, "pubDate")
            summary = _text(item, "description")
            if summary:
                summary = re.sub(r"<[^>]+>", "", summary)[:300]

            articles.append({
                "title": title,
                "url": link,
                "published": pub_date,
                "source": url.split("/")[2],
                "summary": summary,
            })

        # Atom
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("atom:entry", ns):
            title = entry.findtext("atom:title", namespaces=ns)
            link_el = entry.find("atom:link", ns)
            link = link_el.get("href") if link_el is not None else ""
            published = entry.findtext("atom:updated", namespaces=ns) or entry.findtext("atom:published", namespaces=ns)
            summary = entry.findtext("atom:summary", namespaces=ns) or ""
            summary = re.sub(r"<[^>]+>", "", summary)[:300]

            if title:
                articles.append({
                    "title": title,
                    "url": link,
                    "published": published,
                    "source": url.split("/")[2],
                    "summary": summary,
                })

    except Exception as e:
        articles.append({"error": str(e), "source": url})
    return articles


def _fetch_newsapi(api_key: str) -> list:
    articles = []
    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": "NuCana OR NCNA OR Acelarin",
            "sortBy": "publishedAt",
            "pageSize": 20,
            "language": "en",
            "apiKey": api_key,
        }
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        for a in r.json().get("articles", []):
            articles.append({
                "title": a.get("title"),
                "url": a.get("url"),
                "published": a.get("publishedAt"),
                "source": a.get("source", {}).get("name"),
                "summary": (a.get("description") or "")[:300],
            })
    except Exception as e:
        articles.append({"error": str(e)})
    return articles


def _text(el, tag: str) -> str:
    child = el.find(tag)
    return child.text.strip() if child is not None and child.text else ""


def _score_sentiment(text: str) -> str:
    text_lower = text.lower()
    pos = sum(1 for kw in POSITIVE_KEYWORDS if kw in text_lower)
    neg = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text_lower)
    if pos > neg:
        return "positive"
    elif neg > pos:
        return "negative"
    return "neutral"


def _overall_score(sentiments: list) -> float:
    if not sentiments:
        return 0.0
    pos = sentiments.count("positive")
    neg = sentiments.count("negative")
    total = len(sentiments)
    return round((pos - neg) / total, 2)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    data = collect()
    print(json.dumps(data, indent=2, ensure_ascii=False))
