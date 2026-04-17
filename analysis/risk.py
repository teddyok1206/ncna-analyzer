"""
risk.py — 리스크 요인 종합 분석 (바이오텍 특화)
"""

from datetime import datetime


def analyze(financials: dict, market: dict, pipeline: dict, filings: dict, news: dict) -> dict:
    result = {
        "updated_at": datetime.utcnow().isoformat(),
        "risk_score": 0,      # 0(낮음) ~ 10(높음)
        "risks": [],
        "risk_summary": {},
    }

    risks = []

    # 1. 유동성 리스크
    runway = (financials.get("runway") or {})
    runway_months = runway.get("months")
    if runway_months is not None:
        if runway_months < 6:
            risks.append({"level": "critical", "category": "liquidity",
                          "title": "현금 소진 임박",
                          "detail": f"추정 runway {runway_months:.1f}개월. 즉각적 자금 조달 없으면 운영 불가.",
                          "score": 4})
        elif runway_months < 12:
            risks.append({"level": "high", "category": "liquidity",
                          "title": "단기 자금 부족 우려",
                          "detail": f"runway {runway_months:.1f}개월. 12개월 내 추가 자금 조달 필요.",
                          "score": 3})
        elif runway_months < 18:
            risks.append({"level": "medium", "category": "liquidity",
                          "title": "중기 자금 계획 필요",
                          "detail": f"runway {runway_months:.1f}개월.",
                          "score": 1})

    # 2. 희석 리스크 (ATM 발행)
    atm_signals = filings.get("atm_signals", [])
    shelf_offerings = (filings.get("key_filings") or {}).get("shelf_offerings", [])
    if atm_signals or shelf_offerings:
        risks.append({"level": "high", "category": "dilution",
                      "title": "주식 희석 리스크",
                      "detail": f"ATM/shelf offering 감지 {len(atm_signals)}건. 자금 소진 시 추가 발행 가능성.",
                      "score": 2})

    # 3. 임상 실패 리스크
    studies = pipeline.get("studies", [])
    phase3 = [s for s in studies if "3" in s.get("phase", "")]
    phase2 = [s for s in studies if "2" in s.get("phase", "")]
    terminated = [s for s in studies if "Terminat" in s.get("status", "")]

    if terminated:
        risks.append({"level": "high", "category": "pipeline",
                      "title": "임상 중단 이력",
                      "detail": f"{len(terminated)}건의 임상이 종료됨. 파이프라인 집중 리스크.",
                      "score": 2})

    if not phase3 and not phase2:
        risks.append({"level": "medium", "category": "pipeline",
                      "title": "초기 임상 단계",
                      "detail": "Phase 2/3 임상 없음. 상용화까지 장기간 및 대규모 투자 필요.",
                      "score": 2})
    elif phase3:
        risks.append({"level": "medium", "category": "pipeline",
                      "title": f"Phase 3 바이너리 이벤트 {len(phase3)}건",
                      "detail": "Phase 3 결과에 따라 주가 급등/급락 가능. 이분법적 결과.",
                      "score": 2})

    # 4. 시장/유동성 리스크 (소형주)
    info = market.get("info") or {}
    market_cap = info.get("market_cap") or 0
    avg_vol = info.get("avg_volume_10d") or 0

    if market_cap < 50_000_000:  # 5천만 달러 미만
        risks.append({"level": "high", "category": "market",
                      "title": "극소형주 (Micro-cap)",
                      "detail": f"시가총액 ${market_cap:,.0f}. 유동성 부족, 변동성 극대, 기관 참여 제한.",
                      "score": 2})
    elif market_cap < 300_000_000:
        risks.append({"level": "medium", "category": "market",
                      "title": "소형주 (Small-cap)",
                      "detail": f"시가총액 ${market_cap:,.0f}. 변동성 높음.",
                      "score": 1})

    if avg_vol and avg_vol < 100_000:
        risks.append({"level": "medium", "category": "market",
                      "title": "낮은 거래량",
                      "detail": f"10일 평균 거래량 {avg_vol:,}주. 진입/청산 시 슬리피지 위험.",
                      "score": 1})

    # 5. 공매도 리스크
    short_pct = info.get("short_pct_of_float") or 0
    if short_pct > 0.2:
        risks.append({"level": "high", "category": "short_interest",
                      "title": f"높은 공매도 비율 ({short_pct*100:.1f}%)",
                      "detail": "Float의 20% 이상 공매도. 부정적 시장 시각 or 숏스퀴즈 가능성 공존.",
                      "score": 2})
    elif short_pct > 0.1:
        risks.append({"level": "medium", "category": "short_interest",
                      "title": f"주의 공매도 비율 ({short_pct*100:.1f}%)",
                      "detail": "Float의 10% 이상 공매도.",
                      "score": 1})

    # 6. 뉴스 센티멘트 리스크
    sentiment = news.get("sentiment_summary") or {}
    score_val = sentiment.get("score", 0)
    if score_val < -0.3:
        risks.append({"level": "medium", "category": "sentiment",
                      "title": "부정적 뉴스 흐름",
                      "detail": f"최근 뉴스 센티멘트 점수 {score_val:.2f}. 부정적 기사 비중 높음.",
                      "score": 1})

    # 총 리스크 점수 계산
    total_score = sum(r.get("score", 0) for r in risks)
    result["risk_score"] = min(10, total_score)
    result["risks"] = sorted(risks, key=lambda x: x.get("score", 0), reverse=True)

    result["risk_summary"] = {
        "total_risks": len(risks),
        "critical": sum(1 for r in risks if r["level"] == "critical"),
        "high": sum(1 for r in risks if r["level"] == "high"),
        "medium": sum(1 for r in risks if r["level"] == "medium"),
        "overall_level": _overall_level(result["risk_score"]),
    }

    return result


def _overall_level(score: int) -> str:
    if score >= 8:
        return "매우 높음"
    elif score >= 6:
        return "높음"
    elif score >= 4:
        return "보통"
    elif score >= 2:
        return "낮음"
    return "매우 낮음"


if __name__ == "__main__":
    import json
    print(json.dumps(analyze({}, {}, {}, {}, {}), indent=2, ensure_ascii=False))
