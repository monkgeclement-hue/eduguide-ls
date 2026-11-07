from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REAL_DIR = ROOT / "data" / "real"
INSTITUTION = "Bernarda Home Economics School"
POST_URL = (
    "https://www.facebook.com/permalink.php?"
    "story_fbid=pfbid02bjhaGpxRSn1WkTW1aLsPHE1QZAhQzGGgPd1p3TVet17CosBc6tW8NR17vvZJ48RWl"
    "&id=61556281797357"
)
MINISTRY_URL = "https://www.education.gov.ls/education/tvet-institutions"
SOURCE_NOTE = (
    "Transcribed from Bernarda's public Facebook post dated 4 February 2024. "
    "The attached application form is for 2024/25. This is a private admin-review candidate; "
    "confirm the current offering, entry rules, duration, fees, and application process directly with the school."
)


def candidate(record_id: str, name: str, level: str, duration: str, requirements: str, skills: list[str]) -> dict[str, Any]:
    return {
        "id": record_id,
        "institution": INSTITUTION,
        "name": name,
        "category": "Consumer Science & Hospitality",
        "faculty": None,
        "level": level,
        "duration": duration,
        "requirements_summary": requirements,
        "source_url": POST_URL,
        "source_type": "historical_institution_facebook_post",
        "extraction_method": "manual_photo_transcription",
        "review_status": "needs_admin_review",
        "career_options": [],
        "skill_options": skills,
        "source_note": SOURCE_NOTE,
    }


CANDIDATES = [
    candidate(
        "bernarda-certificate-consumer-science-intermediate-2024",
        "Certificate in Consumer Science Intermediate",
        "Certificate",
        "2 years (first- and second-year subjects shown)",
        "JC/Grade 10 with at least five passes, or a COSC/LGCSE/Grade 11 holder. Confirm the current route with the school.",
        ["Food and nutrition", "Clothing and textiles", "Hospitality management", "Horticulture and animal husbandry", "Computer skills", "Entrepreneurship"],
    ),
    candidate(
        "bernarda-operational-skill-2024",
        "Operational Skill",
        "Operational Skill",
        "First- and second-year subjects shown; duration to confirm",
        "The 2024 sheet lists Standard 7 leavers with or without a certificate, and candidates who did not pass JC/Grade 10. Confirm the current route with the school.",
        ["Food and nutrition", "Clothing and textiles", "Hospitality management", "Horticulture and animal husbandry", "Computer skills"],
    ),
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def upsert(items: list[dict[str, Any]], key: str, value: dict[str, Any]) -> None:
    for index, item in enumerate(items):
        if item.get(key) == value.get(key):
            items[index] = value
            return
    items.append(value)


def main() -> None:
    programmes_path = REAL_DIR / "programmes.flat.json"
    programmes = load_json(programmes_path)
    for record in CANDIDATES:
        upsert(programmes, "id", record)
    write_json(programmes_path, programmes)

    by_institution_path = REAL_DIR / "programmes.by-institution.json"
    by_institution = load_json(by_institution_path)
    by_institution[INSTITUTION] = CANDIDATES
    write_json(by_institution_path, dict(sorted(by_institution.items())))
    write_json(REAL_DIR / "institutions" / "bernarda-home-economics-school.json", CANDIDATES)

    summary_path = REAL_DIR / "summary.json"
    summary = load_json(summary_path)
    summary.update({
        "programme_count": len(programmes),
        "institution_count": len({item["institution"] for item in programmes}),
        "institutions": dict(sorted(Counter(item["institution"] for item in programmes).items())),
        "review_status_counts": dict(sorted(Counter(item.get("review_status") or "needs_admin_review" for item in programmes).items())),
        "update_note": "Historical CHE, supplied SIAC/St Elizabeth, and Bernarda 2024 Facebook candidates remain private until current official verification and admin approval.",
    })
    write_json(summary_path, summary)

    audit_path = REAL_DIR / "source-audit.json"
    audit = load_json(audit_path)
    upsert(audit, "source_url", {
        "institution": INSTITUTION,
        "source_url": POST_URL,
        "status": "private_admin_candidate_extract",
        "records_extracted": len(CANDIDATES),
        "data_found": ["two programme routes", "historical entry requirements", "first- and second-year subject lists", "2024/25 application form"],
        "shortage": [
            "Post is dated 4 February 2024 and the attached form is for 2024/25; none of its details establish current admissions.",
            "The form mentions an M200 application-processing amount for 2024/25, not tuition. No current application fee or tuition schedule was found.",
            "Confirm current programme availability, entry rules, duration, fees, and accreditation directly with the school before publication.",
        ],
    })
    upsert(audit, "source_url", {
        "institution": INSTITUTION,
        "source_url": MINISTRY_URL,
        "status": "institution_identity_reference",
        "records_extracted": 0,
        "data_found": ["Bernarda Home Economics listed as TVET institution", "Mekaling, Mohale's Hoek", "registration number 436002"],
        "shortage": ["The ministry listing does not establish current programme offerings, requirements, fees, or accreditation for a specific course."],
    })
    write_json(audit_path, audit)

    coverage_path = REAL_DIR / "source-coverage.json"
    coverage = load_json(coverage_path)
    upsert(coverage, "name", {
        "name": "Bernarda Home Economics School Facebook post (4 February 2024)",
        "url": POST_URL,
        "institution": INSTITUTION,
        "coverage_type": "historical_institution_social_post",
        "status": "private_admin_candidates_only",
        "note": "Two programme leads and a 2024/25 application form were captured. No current tuition or fee schedule was verified; confirm with the school before publishing.",
    })
    upsert(coverage, "name", {
        "name": "Lesotho Ministry of Education TVET institutions listing",
        "url": MINISTRY_URL,
        "institution": INSTITUTION,
        "coverage_type": "government_institution_listing",
        "status": "institution_identity_reference",
        "note": "Supports the school's name, registration number, and Mekaling location, not current programme or fee details.",
    })
    write_json(coverage_path, coverage)

    print(json.dumps({"candidate_count": len(CANDIDATES), "programme_count": len(programmes), "institution_count": summary["institution_count"]}, indent=2))


if __name__ == "__main__":
    main()
