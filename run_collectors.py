"""
run_collectors.py — 모든 데이터 수집 후 data/*.json 저장
GitHub Actions에서도, 로컬에서도 동일하게 실행
"""

import json
import os
import sys
import traceback
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 프로젝트 루트를 path에 추가
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from collectors import market as market_col
from collectors import financials as financials_col
from collectors import pipeline as pipeline_col
from collectors import filings as filings_col
from collectors import news as news_col
from analysis import fundamental as fundamental_ana
from analysis import catalyst as catalyst_ana
from analysis import risk as risk_ana
from analysis import gemini_summary as gemini_ana

DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

TICKER = os.getenv("TICKER", "NCNA")


def save(name: str, data: dict):
    path = DATA_DIR / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    print(f"  ✓ data/{name}.json 저장 완료")


def run():
    print(f"\n{'='*50}")
    print(f"  NCNA 분석 시작 — {TICKER}")
    print(f"{'='*50}\n")

    # ── 1. 데이터 수집 ──────────────────────────────
    print("[1/5] 시장 데이터 수집 중...")
    try:
        market_data = market_col.collect(TICKER)
        save("market", market_data)
    except Exception as e:
        print(f"  ✗ market 수집 실패: {e}")
        market_data = {}

    print("[2/5] 재무 데이터 수집 중...")
    try:
        financials_data = financials_col.collect(TICKER)
        save("financials", financials_data)
    except Exception as e:
        print(f"  ✗ financials 수집 실패: {e}")
        traceback.print_exc()
        financials_data = {}

    print("[3/5] 임상 파이프라인 수집 중...")
    try:
        pipeline_data = pipeline_col.collect()
        save("pipeline", pipeline_data)
    except Exception as e:
        print(f"  ✗ pipeline 수집 실패: {e}")
        pipeline_data = {}

    print("[4/5] SEC 공시 수집 중...")
    try:
        filings_data = filings_col.collect()
        save("filings", filings_data)
    except Exception as e:
        print(f"  ✗ filings 수집 실패: {e}")
        filings_data = {}

    print("[5/5] 뉴스 수집 중...")
    try:
        news_data = news_col.collect()
        save("news", news_data)
    except Exception as e:
        print(f"  ✗ news 수집 실패: {e}")
        news_data = {}

    # ── 2. 분석 ────────────────────────────────────
    print("\n[분석] 펀더멘털 분석 중...")
    try:
        fundamental_data = fundamental_ana.analyze(financials_data, market_data)
        save("fundamental", fundamental_data)
    except Exception as e:
        print(f"  ✗ fundamental 분석 실패: {e}")
        fundamental_data = {}

    print("[분석] 카탈리스트 분석 중...")
    try:
        catalyst_data = catalyst_ana.analyze(pipeline_data, filings_data, news_data)
        save("catalyst", catalyst_data)
    except Exception as e:
        print(f"  ✗ catalyst 분석 실패: {e}")
        catalyst_data = {}

    print("[분석] 리스크 분석 중...")
    try:
        risk_data = risk_ana.analyze(financials_data, market_data, pipeline_data, filings_data, news_data)
        save("risk", risk_data)
    except Exception as e:
        print(f"  ✗ risk 분석 실패: {e}")
        risk_data = {}

    print("[분석] Gemini AI 요약 생성 중...")
    try:
        summary_data = gemini_ana.analyze(
            market_data, financials_data, pipeline_data,
            filings_data, news_data, fundamental_data,
            catalyst_data, risk_data
        )
        save("summary", summary_data)
    except Exception as e:
        print(f"  ✗ Gemini 요약 실패: {e}")
        summary_data = {"error": str(e)}

    print(f"\n{'='*50}")
    print("  완료! data/ 폴더에 저장되었습니다.")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    run()
