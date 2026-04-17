"""
gemini_summary.py — Groq (LLaMA 3.3 70B)으로 전체 데이터 해석/요약 생성
무료 티어: 분당 30 요청, 하루 14,400 요청, 분당 6,000 토큰
"""

import os
import json
from datetime import datetime
from groq import Groq


def analyze(market: dict, financials: dict, pipeline: dict,
            financials_data: dict, news: dict, fundamental: dict,
            catalyst: dict, risk: dict) -> dict:

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {"error": "GROQ_API_KEY not set", "updated_at": datetime.utcnow().isoformat()}

    client = Groq(api_key=api_key)
    context = _build_context(market, financials, pipeline, financials_data, news, fundamental, catalyst, risk)

    prompt = f"""당신은 바이오텍 주식 전문 애널리스트입니다. 아래는 NuCana plc (NCNA)의 최신 데이터입니다.

{context}

위 데이터를 바탕으로 다음을 한국어로 작성하세요:

1. **한줄 요약** (50자 이내): 현재 투자 상황을 가장 압축적으로
2. **강점** (3개, 각 2-3문장): 투자 근거가 될 수 있는 요소
3. **리스크** (3개, 각 2-3문장): 주요 우려 요인
4. **핵심 카탈리스트** (2개): 주가에 가장 큰 영향을 줄 이벤트
5. **투자 관점 종합** (5-7문장): 종합적 판단, 어떤 투자자에게 적합한지
6. **주의사항**: 이 분석의 한계 한 줄

반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 포함하지 마세요:
{{
  "one_liner": "...",
  "strengths": ["...", "...", "..."],
  "risks": ["...", "...", "..."],
  "key_catalysts": ["...", "..."],
  "investment_view": "...",
  "disclaimer": "..."
}}"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2048,
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content.strip()
        parsed = json.loads(text)
        parsed["updated_at"] = datetime.utcnow().isoformat()
        parsed["model"] = "groq/llama-3.3-70b-versatile"
        return parsed

    except Exception as e:
        return {
            "error": str(e),
            "updated_at": datetime.utcnow().isoformat(),
        }


def _build_context(market, financials, pipeline, filings, news, fundamental, catalyst, risk) -> str:
    lines = []

    price = market.get("price", {})
    tech  = market.get("technicals", {})
    info  = market.get("info") or {}
    lines.append("## 주가 현황")
    lines.append(f"- 현재가: ${price.get('current', 'N/A')}")
    lines.append(f"- 등락: {price.get('change_pct', 'N/A')}%")
    lines.append(f"- 52주 고가 대비: {price.get('pct_from_52w_high', 'N/A')}%")
    lines.append(f"- RSI: {tech.get('rsi_14', 'N/A')}")
    lines.append(f"- 시가총액: ${info.get('market_cap', 'N/A'):,}" if info.get("market_cap") else "- 시가총액: N/A")
    lines.append(f"- 공매도 비율: {(info.get('short_pct_of_float') or 0)*100:.1f}%")

    bs     = financials.get("balance_sheet") or {}
    runway = financials.get("runway") or {}
    burn   = financials.get("burn_rate") or {}
    lines.append("\n## 재무 현황")
    lines.append(f"- 현금 잔고: ${bs.get('latest_cash', 'N/A'):,}" if bs.get("latest_cash") else "- 현금 잔고: N/A")
    lines.append(f"- 월 소각률: ${abs(burn.get('avg_monthly_burn') or 0):,}" if burn.get("avg_monthly_burn") else "- 월 소각률: N/A")
    lines.append(f"- Runway: {runway.get('months', 'N/A')}개월 ({runway.get('assessment', '')})")

    summary = pipeline.get("summary", {})
    lines.append("\n## 임상 파이프라인")
    lines.append(f"- 총 임상 수: {summary.get('total', 0)}")
    lines.append(f"- 단계별: {summary.get('by_phase', {})}")
    lines.append(f"- 현재 모집 중: {len(summary.get('recruiting', []))}건")
    lines.append(f"- 중단/종료: {summary.get('by_status', {}).get('TERMINATED', 0)}건")

    upcoming = catalyst.get("upcoming_catalysts", [])[:3]
    lines.append("\n## 주요 카탈리스트")
    for c in upcoming:
        lines.append(f"- {c.get('drug')}: {c.get('phase')} / {c.get('status')} / 완료예정: {c.get('primary_completion', 'N/A')}")

    risks = risk.get("risks", [])[:5]
    lines.append(f"\n## 주요 리스크 (리스크 점수: {risk.get('risk_score', 0)}/10)")
    for r in risks:
        lines.append(f"- [{r.get('level','').upper()}] {r.get('title')}: {r.get('detail','')[:100]}")

    sentiment = news.get("sentiment_summary", {})
    recent_news = news.get("articles", [])[:5]
    lines.append("\n## 뉴스 센티멘트")
    lines.append(f"- 점수: {sentiment.get('score', 0)} (긍정:{sentiment.get('positive',0)} / 부정:{sentiment.get('negative',0)} / 중립:{sentiment.get('neutral',0)})")
    for a in recent_news:
        lines.append(f"- [{a.get('sentiment','')}] {a.get('title','')[:80]}")

    atm = filings.get("atm_signals", [])
    if atm:
        lines.append(f"\n## 희석 이벤트")
        lines.append(f"- ATM/Shelf offering {len(atm)}건 감지")

    return "\n".join(lines)
