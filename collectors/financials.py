"""
financials.py — 재무제표 수집 (yfinance + SEC EDGAR)
핵심 지표: 현금 잔고, 분기 burn rate, runway 추정
"""

import yfinance as yf
import requests
import json
from datetime import datetime


EDGAR_BASE = "https://data.sec.gov/submissions"
EDGAR_FACTS = "https://data.sec.gov/api/xbrl/companyfacts"
HEADERS = {"User-Agent": "NCNA-Analyzer research@example.com"}


def _get_cik(ticker: str) -> str | None:
    """티커 → CIK 번호 조회"""
    url = "https://efts.sec.gov/LATEST/search-index?q=%22{}%22&dateRange=custom&startdt=2020-01-01&forms=20-F".format(ticker)
    # 티커-CIK 매핑 파일 사용
    mapping_url = "https://www.sec.gov/files/company_tickers.json"
    try:
        r = requests.get(mapping_url, headers=HEADERS, timeout=10)
        data = r.json()
        for item in data.values():
            if item.get("ticker", "").upper() == ticker.upper():
                return str(item["cik_str"]).zfill(10)
    except Exception:
        pass
    return None


def collect(ticker: str = "NCNA") -> dict:
    stock = yf.Ticker(ticker)
    result = {
        "ticker": ticker,
        "updated_at": datetime.utcnow().isoformat(),
        "balance_sheet": {},
        "income_statement": {},
        "cash_flow": {},
        "burn_rate": {},
        "runway": None,
        "key_metrics": {},
    }

    # --- yfinance 재무제표 ---
    try:
        bs = stock.quarterly_balance_sheet
        if not bs.empty:
            # 최근 4분기 현금 잔고
            cash_rows = [r for r in bs.index if "Cash" in str(r)]
            cash_series = {}
            for row in cash_rows:
                for col in bs.columns[:4]:
                    val = bs.loc[row, col]
                    if not _isnan(val):
                        date_str = str(col.date()) if hasattr(col, 'date') else str(col)
                        cash_series[date_str] = int(val)
                        break

            result["balance_sheet"] = {
                "cash_history": cash_series,
                "latest_cash": list(cash_series.values())[0] if cash_series else None,
                "latest_date": list(cash_series.keys())[0] if cash_series else None,
            }
    except Exception as e:
        result["balance_sheet"]["error"] = str(e)

    try:
        cf = stock.quarterly_cashflow
        if not cf.empty:
            op_rows = [r for r in cf.index if "Operating" in str(r)]
            op_cash = {}
            for row in op_rows:
                for col in cf.columns[:4]:
                    val = cf.loc[row, col]
                    date_str = str(col.date()) if hasattr(col, 'date') else str(col)
                    if not _isnan(val):
                        op_cash[date_str] = int(val)

            # Burn rate = 영업활동 현금흐름 (음수면 소모 중)
            if op_cash:
                recent_vals = list(op_cash.values())[:4]
                avg_burn = sum(recent_vals) / len(recent_vals)
                result["cash_flow"] = {"quarterly_operating_cf": op_cash}
                result["burn_rate"] = {
                    "avg_quarterly_burn": int(avg_burn),
                    "avg_monthly_burn": int(avg_burn / 3),
                    "is_cash_burning": avg_burn < 0,
                }

                # Runway 계산
                latest_cash = result["balance_sheet"].get("latest_cash")
                if latest_cash and avg_burn < 0:
                    runway_months = latest_cash / abs(avg_burn / 3)
                    result["runway"] = {
                        "months": round(runway_months, 1),
                        "years": round(runway_months / 12, 1),
                        "assessment": _assess_runway(runway_months),
                    }
    except Exception as e:
        result["cash_flow"]["error"] = str(e)

    try:
        inc = stock.quarterly_income_stmt
        if not inc.empty:
            rev_rows = [r for r in inc.index if "Revenue" in str(r) or "revenue" in str(r).lower()]
            rd_rows = [r for r in inc.index if "Research" in str(r)]
            revenues = {}
            rd_expenses = {}

            for col in inc.columns[:4]:
                date_str = str(col.date()) if hasattr(col, 'date') else str(col)
                for row in rev_rows:
                    val = inc.loc[row, col]
                    if not _isnan(val):
                        revenues[date_str] = int(val)
                        break
                for row in rd_rows:
                    val = inc.loc[row, col]
                    if not _isnan(val):
                        rd_expenses[date_str] = int(val)
                        break

            result["income_statement"] = {
                "quarterly_revenue": revenues,
                "quarterly_rd_expense": rd_expenses,
            }
    except Exception as e:
        result["income_statement"]["error"] = str(e)

    # --- 핵심 지표 요약 ---
    try:
        info = stock.info
        result["key_metrics"] = {
            "market_cap": info.get("marketCap"),
            "enterprise_value": info.get("enterpriseValue"),
            "total_cash": info.get("totalCash"),
            "total_debt": info.get("totalDebt"),
            "operating_cash_flow": info.get("operatingCashflow"),
            "free_cash_flow": info.get("freeCashflow"),
            "revenue_ttm": info.get("totalRevenue"),
            "employees": info.get("fullTimeEmployees"),
        }
    except Exception:
        pass

    return result


def _isnan(val) -> bool:
    try:
        import math
        return math.isnan(float(val))
    except Exception:
        return True


def _assess_runway(months: float) -> str:
    if months >= 24:
        return "안전 (24개월 이상)"
    elif months >= 12:
        return "주의 (12~24개월)"
    elif months >= 6:
        return "위험 (6~12개월)"
    else:
        return "긴급 (6개월 미만)"


if __name__ == "__main__":
    data = collect("NCNA")
    print(json.dumps(data, indent=2, ensure_ascii=False))
