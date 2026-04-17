"""
fundamental.py — 펀더멘털 분석 (바이오텍 특화)
"""

from datetime import datetime


def analyze(financials: dict, market: dict) -> dict:
    result = {
        "updated_at": datetime.utcnow().isoformat(),
        "scores": {},
        "flags": [],
        "summary": {},
    }

    market_cap = (market.get("info") or {}).get("market_cap") or 0
    latest_cash = (financials.get("balance_sheet") or {}).get("latest_cash") or 0
    runway = financials.get("runway") or {}
    burn = financials.get("burn_rate") or {}
    km = financials.get("key_metrics") or {}

    # --- 현금 vs 시가총액 비율 ---
    cash_to_mc = (latest_cash / market_cap * 100) if market_cap > 0 else 0
    result["summary"]["cash_to_market_cap_pct"] = round(cash_to_mc, 1)

    if cash_to_mc >= 50:
        result["flags"].append({
            "type": "bullish",
            "category": "valuation",
            "note": f"현금이 시가총액의 {cash_to_mc:.0f}% — 하방 지지력 높음",
        })
    elif cash_to_mc < 20:
        result["flags"].append({
            "type": "bearish",
            "category": "valuation",
            "note": f"현금이 시가총액의 {cash_to_mc:.0f}% — 가치 대비 현금 비중 낮음",
        })

    # --- Runway ---
    runway_months = runway.get("months")
    if runway_months:
        result["summary"]["runway_months"] = runway_months
        result["summary"]["runway_assessment"] = runway.get("assessment")

        if runway_months < 6:
            result["flags"].append({
                "type": "critical",
                "category": "liquidity",
                "note": f"runway {runway_months:.1f}개월 — 긴급 자금 조달 필요",
            })
        elif runway_months < 12:
            result["flags"].append({
                "type": "warning",
                "category": "liquidity",
                "note": f"runway {runway_months:.1f}개월 — 12개월 내 추가 자금 필요 가능성",
            })

    # --- Burn Rate ---
    monthly_burn = burn.get("avg_monthly_burn")
    if monthly_burn and monthly_burn < 0:
        result["summary"]["monthly_burn_usd"] = monthly_burn
        result["flags"].append({
            "type": "neutral",
            "category": "burn",
            "note": f"월 평균 소각: ${abs(monthly_burn):,.0f} (임상 진행 중 정상 범위 가능)",
        })

    # --- 매출 여부 (바이오텍 초기는 0이 정상) ---
    revenue = (financials.get("income_statement") or {}).get("quarterly_revenue") or {}
    has_revenue = any(v > 0 for v in revenue.values()) if revenue else False
    result["summary"]["has_revenue"] = has_revenue
    if not has_revenue:
        result["flags"].append({
            "type": "neutral",
            "category": "revenue",
            "note": "매출 없음 — 임상 단계 바이오텍 (pipeline value에 집중)",
        })

    # --- R&D 지출 vs 총비용 ---
    rd = (financials.get("income_statement") or {}).get("quarterly_rd_expense") or {}
    if rd:
        latest_rd = list(rd.values())[0] if rd else 0
        result["summary"]["latest_quarterly_rd"] = latest_rd

    # --- 점수 (0~10) ---
    score = 5
    if cash_to_mc >= 50:
        score += 2
    elif cash_to_mc >= 30:
        score += 1
    if runway_months:
        if runway_months >= 24:
            score += 2
        elif runway_months >= 12:
            score += 1
        elif runway_months < 6:
            score -= 3
        elif runway_months < 12:
            score -= 1

    result["scores"]["fundamental"] = max(0, min(10, score))

    return result


if __name__ == "__main__":
    import json
    print(json.dumps(analyze({}, {}), indent=2, ensure_ascii=False))
