"""
filings.py — SEC EDGAR 공시 수집 (20-F, 6-K, DEF14A 등)
NuCana는 외국 민간 발행자(FPI)라 20-F/6-K 사용
"""

import requests
import json
from datetime import datetime


HEADERS = {"User-Agent": "NCNA-Analyzer research@example.com"}
EDGAR_SUBMISSIONS = "https://data.sec.gov/submissions"
EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"

# NuCana CIK (SEC에 등록된 고정값)
NUCANA_CIK = "0001709626"

IMPORTANT_FORMS = {"20-F", "6-K", "DEF 14A", "SC 13G", "SC 13G/A", "424B3", "F-3"}


def collect(cik: str = NUCANA_CIK) -> dict:
    result = {
        "cik": cik,
        "updated_at": datetime.utcnow().isoformat(),
        "company_info": {},
        "recent_filings": [],
        "key_filings": {
            "annual_reports": [],
            "current_reports": [],
            "proxy": [],
            "shelf_offerings": [],
        },
    }

    try:
        # EDGAR submissions API
        url = f"{EDGAR_SUBMISSIONS}/CIK{cik}.json"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()

        result["company_info"] = {
            "name": data.get("name"),
            "ticker": data.get("tickers", [None])[0],
            "exchange": data.get("exchanges", [None])[0],
            "sic": data.get("sic"),
            "sic_description": data.get("sicDescription"),
            "state_of_inc": data.get("stateOfIncorporation"),
            "fiscal_year_end": data.get("fiscalYearEnd"),
            "ein": data.get("ein"),
        }

        filings = data.get("filings", {}).get("recent", {})
        forms = filings.get("form", [])
        dates = filings.get("filingDate", [])
        accessions = filings.get("accessionNumber", [])
        descriptions = filings.get("primaryDocument", [])
        doc_descriptions = filings.get("primaryDocDescription", [])

        for i, (form, date, acc, doc, desc) in enumerate(
            zip(forms, dates, accessions, descriptions, doc_descriptions)
        ):
            if i >= 50:
                break

            acc_clean = acc.replace("-", "")
            filing_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_clean}/{doc}"
            index_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type={form}&dateb=&owner=include&count=10"

            entry = {
                "form": form,
                "date": date,
                "accession": acc,
                "document": doc,
                "description": desc,
                "url": filing_url,
                "index_url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_clean}/",
            }

            result["recent_filings"].append(entry)

            # 분류
            if form == "20-F":
                result["key_filings"]["annual_reports"].append(entry)
            elif form == "6-K":
                result["key_filings"]["current_reports"].append(entry)
            elif form in {"DEF 14A", "PRE 14A"}:
                result["key_filings"]["proxy"].append(entry)
            elif form in {"424B3", "F-3", "F-3ASR"}:
                result["key_filings"]["shelf_offerings"].append(entry)

        # 각 카테고리 최근 10건만
        for key in result["key_filings"]:
            result["key_filings"][key] = result["key_filings"][key][:10]

        # ATM(At-the-Market) 발행 감지 — 희석 리스크 핵심
        atm_signals = []
        for f in result["recent_filings"]:
            if f["form"] in {"424B3", "F-3"} or "prospectus" in f["description"].lower():
                atm_signals.append({
                    "date": f["date"],
                    "form": f["form"],
                    "url": f["url"],
                })
        result["atm_signals"] = atm_signals

    except Exception as e:
        result["error"] = str(e)

    return result


if __name__ == "__main__":
    data = collect()
    print(json.dumps(data, indent=2, ensure_ascii=False))
