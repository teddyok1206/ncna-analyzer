"""
pipeline.py — NuCana 임상시험 현황 수집 (ClinicalTrials.gov API v2)
"""

import requests
import json
from datetime import datetime


CT_API = "https://clinicaltrials.gov/api/v2/studies"


NUCANA_DRUGS = [
    "Acelarin",
    "NUC-1031",
    "NUC-3373",
    "NUC-7738",
    "NuCana",
]


def collect() -> dict:
    result = {
        "updated_at": datetime.utcnow().isoformat(),
        "studies": [],
        "summary": {},
    }

    seen_ids = set()

    for drug in NUCANA_DRUGS:
        studies = _fetch_studies(drug)
        for s in studies:
            nct_id = s.get("nct_id")
            if nct_id and nct_id not in seen_ids:
                seen_ids.add(nct_id)
                result["studies"].append(s)

    # 요약 통계
    phases = {}
    statuses = {}
    for s in result["studies"]:
        ph = s.get("phase", "Unknown")
        st = s.get("status", "Unknown")
        phases[ph] = phases.get(ph, 0) + 1
        statuses[st] = statuses.get(st, 0) + 1

    result["summary"] = {
        "total": len(result["studies"]),
        "by_phase": phases,
        "by_status": statuses,
        "recruiting": [s for s in result["studies"] if "Recruiting" in s.get("status", "")],
        "completed": [s for s in result["studies"] if "Completed" in s.get("status", "")],
    }

    return result


def _fetch_studies(query: str) -> list:
    params = {
        "query.intr": query,
        "pageSize": 20,
        "format": "json",
        "fields": ",".join([
            "NCTId", "BriefTitle", "OverallStatus", "Phase",
            "Condition", "StartDate", "PrimaryCompletionDate",
            "CompletionDate", "EnrollmentCount", "LeadSponsorName",
            "BriefSummary", "StudyType", "LastUpdatePostDate",
        ]),
    }
    try:
        r = requests.get(CT_API, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        studies = []
        for item in data.get("studies", []):
            proto = item.get("protocolSection", {})
            id_mod = proto.get("identificationModule", {})
            status_mod = proto.get("statusModule", {})
            design_mod = proto.get("designModule", {})
            desc_mod = proto.get("descriptionModule", {})
            sponsor_mod = proto.get("sponsorCollaboratorsModule", {})
            cond_mod = proto.get("conditionsModule", {})

            studies.append({
                "nct_id": id_mod.get("nctId"),
                "title": id_mod.get("briefTitle"),
                "status": status_mod.get("overallStatus"),
                "phase": _parse_phase(design_mod.get("phases", [])),
                "conditions": cond_mod.get("conditions", []),
                "start_date": status_mod.get("startDateStruct", {}).get("date"),
                "primary_completion": status_mod.get("primaryCompletionDateStruct", {}).get("date"),
                "completion_date": status_mod.get("completionDateStruct", {}).get("date"),
                "enrollment": design_mod.get("enrollmentInfo", {}).get("count"),
                "sponsor": sponsor_mod.get("leadSponsor", {}).get("name"),
                "summary": desc_mod.get("briefSummary", "")[:500],
                "last_updated": status_mod.get("lastUpdatePostDateStruct", {}).get("date"),
                "url": f"https://clinicaltrials.gov/study/{id_mod.get('nctId')}",
            })
        return studies
    except Exception as e:
        return [{"error": str(e), "query": query}]


def _parse_phase(phases: list) -> str:
    if not phases:
        return "N/A"
    clean = [p.replace("PHASE", "Phase ").replace("_", "/") for p in phases]
    return ", ".join(clean)


if __name__ == "__main__":
    data = collect()
    print(json.dumps(data, indent=2, ensure_ascii=False))
