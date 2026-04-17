"""
catalyst.py — 임상 카탈리스트 캘린더 생성
"""

from datetime import datetime, date
import re


def analyze(pipeline: dict, filings: dict, news: dict) -> dict:
    result = {
        "updated_at": datetime.utcnow().isoformat(),
        "upcoming_catalysts": [],
        "recent_catalysts": [],
        "catalyst_score": 0,
        "flags": [],
    }

    today = date.today()
    studies = pipeline.get("studies", [])

    for s in studies:
        nct_id = s.get("nct_id", "")
        title = s.get("title", "")
        status = s.get("status", "")
        phase = s.get("phase", "")
        primary_completion = s.get("primary_completion")
        completion = s.get("completion_date")
        last_updated = s.get("last_updated")

        # 약물명 추출
        drug = _extract_drug(title)

        # Primary completion date 파싱
        pcd = _parse_date(primary_completion)
        cd = _parse_date(completion)
        lu = _parse_date(last_updated)

        catalyst = {
            "nct_id": nct_id,
            "drug": drug,
            "title": title,
            "phase": phase,
            "status": status,
            "primary_completion": primary_completion,
            "completion_date": completion,
            "last_updated": last_updated,
            "url": s.get("url"),
            "enrollment": s.get("enrollment"),
            "conditions": s.get("conditions", []),
            "catalyst_type": _classify_catalyst(phase, status),
            "importance": _score_importance(phase, status),
        }

        if pcd and pcd >= today:
            catalyst["days_until_completion"] = (pcd - today).days
            result["upcoming_catalysts"].append(catalyst)
        elif pcd and pcd < today:
            catalyst["days_since_completion"] = (today - pcd).days
            result["recent_catalysts"].append(catalyst)
        elif status in ("Recruiting", "Active, not recruiting"):
            result["upcoming_catalysts"].append(catalyst)

    # 최근성 정렬
    result["upcoming_catalysts"].sort(key=lambda x: x.get("days_until_completion", 9999))
    result["recent_catalysts"].sort(key=lambda x: x.get("days_since_completion", 9999))

    # 공시 기반 카탈리스트 (6-K에서 임상 관련 발표 감지)
    filing_catalysts = _extract_filing_catalysts(filings)
    result["filing_based_catalysts"] = filing_catalysts

    # 뉴스 기반 카탈리스트 감지
    news_catalysts = _extract_news_catalysts(news)
    result["news_based_catalysts"] = news_catalysts

    # 카탈리스트 점수 (0~10)
    score = 0
    for c in result["upcoming_catalysts"]:
        score += c.get("importance", 0)
    result["catalyst_score"] = min(10, score)

    # 플래그
    phase3_upcoming = [c for c in result["upcoming_catalysts"] if "3" in c.get("phase", "")]
    if phase3_upcoming:
        result["flags"].append({
            "type": "bullish",
            "note": f"Phase 3 임상 완료 예정 {len(phase3_upcoming)}건 — 주요 카탈리스트",
        })

    recruiting = [c for c in result["upcoming_catalysts"] if c.get("status") == "Recruiting"]
    if recruiting:
        result["flags"].append({
            "type": "neutral",
            "note": f"현재 모집 중인 임상 {len(recruiting)}건",
        })

    return result


def _extract_drug(title: str) -> str:
    patterns = {
        "Acelarin / NUC-1031": r"acelarin|nuc.?1031",
        "NUC-3373": r"nuc.?3373",
        "NUC-7738": r"nuc.?7738",
        "NUC-3373": r"nuc.?3373",
    }
    title_lower = title.lower()
    for drug, pattern in patterns.items():
        if re.search(pattern, title_lower):
            return drug
    return "NuCana (unspecified)"


def _parse_date(date_str: str | None) -> date | None:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%B %d, %Y", "%Y-%m", "%B %Y"):
        try:
            return datetime.strptime(date_str[:10] if len(date_str) > 10 else date_str, fmt).date()
        except ValueError:
            pass
    return None


def _classify_catalyst(phase: str, status: str) -> str:
    if "3" in phase:
        return "Phase 3 Data Readout"
    elif "2" in phase:
        return "Phase 2 Data Readout"
    elif "1" in phase:
        return "Phase 1 Safety/Dose"
    return "Clinical Update"


def _score_importance(phase: str, status: str) -> int:
    score = 0
    if "3" in phase:
        score += 4
    elif "2" in phase:
        score += 2
    elif "1" in phase:
        score += 1
    if status in ("Active, not recruiting", "Completed"):
        score += 1
    return score


def _extract_filing_catalysts(filings: dict) -> list:
    catalysts = []
    for filing in (filings.get("key_filings") or {}).get("current_reports", [])[:10]:
        desc = filing.get("description", "").lower()
        if any(kw in desc for kw in ["clinical", "trial", "data", "result", "efficacy"]):
            catalysts.append({
                "date": filing.get("date"),
                "type": "6-K",
                "description": filing.get("description"),
                "url": filing.get("url"),
            })
    return catalysts


def _extract_news_catalysts(news: dict) -> list:
    catalysts = []
    catalyst_keywords = [
        "phase", "trial", "data", "result", "fda", "approval",
        "efficacy", "endpoint", "enrollment", "interim", "readout",
    ]
    for a in (news.get("articles") or [])[:20]:
        title = (a.get("title") or "").lower()
        if any(kw in title for kw in catalyst_keywords):
            catalysts.append({
                "date": a.get("published"),
                "title": a.get("title"),
                "url": a.get("url"),
                "sentiment": a.get("sentiment"),
            })
    return catalysts[:10]


if __name__ == "__main__":
    import json
    print(json.dumps(analyze({}, {}, {}), indent=2, ensure_ascii=False))
