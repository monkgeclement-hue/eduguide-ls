from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REAL_DIR = ROOT / "data" / "real"
PROGRAMMES_PATH = REAL_DIR / "programmes.flat.json"
BY_INSTITUTION_PATH = REAL_DIR / "programmes.by-institution.json"
SUMMARY_PATH = REAL_DIR / "summary.json"
SOURCE_AUDIT_PATH = REAL_DIR / "source-audit.json"
COVERAGE_PATH = REAL_DIR / "source-coverage.json"

SIAC = "St Mary's Integrative Applied College (SIAC)"
ST_ELIZABETH = "St Elizabeth College"
SIAC_SOURCE = "data/references/siac-prospectus-2025-2026.pdf"
ST_ELIZABETH_SOURCE = "data/references/st-elizabeth-college-subject-prospectus-supplied.pdf"

SIAC_NOTE = (
    "Extracted from the supplied SIAC 2025-2026 prospectus (programme details on page 2). "
    "This is a private admin-review candidate: confirm current programme availability, admissions, fees, "
    "application dates, and accreditation before publishing it to students."
)
ST_ELIZABETH_NOTE = (
    "Extracted from college information supplied by the project owner and preserved as a source PDF. "
    "The material has no publication date, fee schedule, official contact details, or application link. "
    "Keep this private until the college confirms current availability and requirements."
)


def candidate(
    record_id: str,
    institution: str,
    name: str,
    category: str,
    faculty: str,
    level: str,
    duration: str,
    requirements: str,
    source_path: str,
    source_type: str,
    extraction_method: str,
    source_note: str,
    careers: list[str] | None = None,
    skills: list[str] | None = None,
    application_window: str | None = None,
    fee_note: str | None = None,
) -> dict[str, Any]:
    record = {
        "id": record_id,
        "institution": institution,
        "name": name,
        "category": category,
        "faculty": faculty,
        "level": level,
        "duration": duration,
        "requirements_summary": requirements,
        "source_url": None,
        "source_path": source_path,
        "source_type": source_type,
        "extraction_method": extraction_method,
        "review_status": "needs_admin_review",
        "career_options": careers or [],
        "skill_options": skills or [],
        "source_note": source_note,
    }
    if application_window:
        record["application_window"] = application_window
    if fee_note:
        record["fee_note"] = fee_note
    return record


SIAC_CANDIDATES = [
    candidate(
        "siac-national-craft-certificate-consumer-science-advanced-2025-2026",
        SIAC,
        "National Craft Certificate in Consumer Science Advanced (NCC)",
        "Consumer Science & Hospitality",
        "Consumer Science",
        "National Craft Certificate",
        "2 years",
        "COSC/LGCSE with five passes.",
        SIAC_SOURCE,
        "supplied_institution_prospectus_pdf",
        "pdf_text_extract",
        SIAC_NOTE,
        ["Self-employment", "Teacher", "Chef", "Fashion Designer", "Nutritionist", "Food Scientist", "Dietician", "Hotel Manager"],
        ["Clothing and textiles", "Food and nutrition", "Hospitality", "Customer care", "Baking", "Preservation", "Computer skills", "Entrepreneurship"],
        fee_note="The supplied 2025-2026 prospectus lists M7,000 total annual fees, a M4,100 minimum deposit including chef uniform, and M2,900 balance. Confirm all amounts before payment.",
    ),
    candidate(
        "siac-national-vocational-certificate-consumer-science-2025-2026",
        SIAC,
        "National Vocational Certificate in Consumer Science (NVC)",
        "Consumer Science & Hospitality",
        "Consumer Science",
        "National Vocational Certificate",
        "2 years",
        "Junior Certificate (JC) or three passes in LGCSE.",
        SIAC_SOURCE,
        "supplied_institution_prospectus_pdf",
        "pdf_text_extract",
        SIAC_NOTE,
        ["Self-employment", "Cook", "Housekeeper", "Waiter or Waitress", "Farmer"],
        ["Clothing and textiles", "Food and nutrition", "Hospitality", "Customer care", "Baking", "Arts and crafts", "Computer applications", "Entrepreneurship"],
        fee_note="The supplied 2025-2026 prospectus lists M7,000 total annual fees, a M4,100 minimum deposit including chef uniform, and M2,900 balance. Confirm all amounts before payment.",
    ),
    candidate(
        "siac-basic-operative-certificate-consumer-science-2025-2026",
        SIAC,
        "Basic Operative Certificate in Consumer Science (BOC)",
        "Consumer Science & Hospitality",
        "Consumer Science",
        "Basic Operative Certificate",
        "1 year",
        "Special education programme for intellectually disabled or impaired youth. Entry states age 17 years and above with PSLE/Grade 7 education.",
        SIAC_SOURCE,
        "supplied_institution_prospectus_pdf",
        "pdf_text_extract",
        SIAC_NOTE,
        ["Self-employment", "Cook", "Housekeeper", "Sewing Industry Worker", "Farmer"],
        ["Basic sewing", "Catering and hospitality", "Decoration", "Food production", "Baking", "Preservation", "Numeracy", "Computer skills"],
        fee_note="The supplied 2025-2026 prospectus lists M7,000 total annual fees, a M4,100 minimum deposit including chef uniform, and M2,900 balance. Confirm all amounts before payment.",
    ),
    candidate(
        "siac-diploma-tourism-travel-management-2025-2026",
        SIAC,
        "Diploma in Tourism and Travel Management (DTTM)",
        "Travel & Tourism",
        "Tourism and Travel",
        "Diploma",
        "3 years",
        "COSC/LGCSE with two credits including English Language and Geography or History, plus D or better in three other subjects; or a National Craft Certificate in Consumer Science passed with credit or better.",
        SIAC_SOURCE,
        "supplied_institution_prospectus_pdf",
        "pdf_text_extract",
        SIAC_NOTE,
        application_window="February to May",
        fee_note="The supplied 2025-2026 prospectus lists M15,640 total fees, a M7,000 minimum deposit, then two M4,320 balances with dates printed as 30 November 2027 and 28 February 2027. Confirm the fee year and dates before payment.",
    ),
    candidate(
        "siac-national-craft-certificate-fashion-design-modular-2025-2026",
        SIAC,
        "National Craft Certificate in Fashion Design Modular (NCCFDM)",
        "Fashion & Design",
        "Fashion Design",
        "National Craft Certificate",
        "6 months",
        "Credit or better in National Vocational Certificate in Consumer Science; or pass or better in National Craft Certificate in Consumer Science; or COSC/LGCSE with a credit in Fashion Design, four passes in other subjects, and a passed pre-entry course.",
        SIAC_SOURCE,
        "supplied_institution_prospectus_pdf",
        "pdf_text_extract",
        SIAC_NOTE,
        skills=["Pattern drafting", "Garment construction"],
        application_window="February to June",
        fee_note="The supplied 2025-2026 prospectus lists M8,750 total fees, a M6,000 minimum deposit including a pattern-drafting kit, and M2,750 balance. Confirm all amounts before payment.",
    ),
]

ST_ELIZABETH_CANDIDATES = [
    candidate(
        "st-elizabeth-certificate-consumer-science-supplied",
        ST_ELIZABETH,
        "Certificate in Consumer Science",
        "Consumer Science & Hospitality",
        "Consumer Science",
        "Certificate",
        "2 years",
        "COSC/LGCSE with at least five passes including English Language and a related subject.",
        ST_ELIZABETH_SOURCE,
        "manual_user_confirmation_prospectus_pdf",
        "manual_supplied_text_to_pdf",
        ST_ELIZABETH_NOTE,
    ),
    candidate(
        "st-elizabeth-diploma-consumer-science-supplied",
        ST_ELIZABETH,
        "Diploma in Consumer Science",
        "Consumer Science & Hospitality",
        "Consumer Science",
        "Diploma",
        "3 years",
        "COSC/LGCSE with two credits and at least three passes in related subjects including English Language at D or better; or COSC/LGCSE plus a Certificate in Home Science Advanced or Consumer Science.",
        ST_ELIZABETH_SOURCE,
        "manual_user_confirmation_prospectus_pdf",
        "manual_supplied_text_to_pdf",
        ST_ELIZABETH_NOTE,
    ),
    candidate(
        "st-elizabeth-certificate-business-management-supplied",
        ST_ELIZABETH,
        "Certificate in Business Management",
        "Business & Commerce",
        "Commercial Department",
        "Certificate",
        "2 years",
        "COSC/LGCSE with at least five passes including English Language, Mathematics, and a related commercial subject.",
        ST_ELIZABETH_SOURCE,
        "manual_user_confirmation_prospectus_pdf",
        "manual_supplied_text_to_pdf",
        ST_ELIZABETH_NOTE,
    ),
    candidate(
        "st-elizabeth-diploma-business-management-supplied",
        ST_ELIZABETH,
        "Diploma in Business Management",
        "Business & Commerce",
        "Commercial Department",
        "Diploma",
        "3 years",
        "COSC/LGCSE with two credits and at least three passes including English Language, Mathematics, and a related commercial subject at D or better; or a Certificate in Business Management from a recognised institute.",
        ST_ELIZABETH_SOURCE,
        "manual_user_confirmation_prospectus_pdf",
        "manual_supplied_text_to_pdf",
        ST_ELIZABETH_NOTE,
    ),
    candidate(
        "st-elizabeth-certificate-office-administration-supplied",
        ST_ELIZABETH,
        "Certificate in Office Administration",
        "Business & Commerce",
        "Commercial Department",
        "Certificate",
        "2 years",
        "COSC/LGCSE with at least five passes including English Language and a related commercial subject.",
        ST_ELIZABETH_SOURCE,
        "manual_user_confirmation_prospectus_pdf",
        "manual_supplied_text_to_pdf",
        ST_ELIZABETH_NOTE,
    ),
    candidate(
        "st-elizabeth-diploma-office-administration-supplied",
        ST_ELIZABETH,
        "Diploma in Office Administration",
        "Business & Commerce",
        "Commercial Department",
        "Diploma",
        "3 years",
        "COSC/LGCSE with two credits and at least three passes, including English Language at D or better and a related subject; or a Certificate in Office Administration from a recognised institute.",
        ST_ELIZABETH_SOURCE,
        "manual_user_confirmation_prospectus_pdf",
        "manual_supplied_text_to_pdf",
        ST_ELIZABETH_NOTE,
    ),
]

CANDIDATES = SIAC_CANDIDATES + ST_ELIZABETH_CANDIDATES


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def upsert_by_key(items: list[dict[str, Any]], key: str, value: dict[str, Any]) -> None:
    for index, item in enumerate(items):
        if item.get(key) == value.get(key):
            items[index] = value
            return
    items.append(value)


def main() -> None:
    programmes = load_json(PROGRAMMES_PATH)
    positions = {str(item.get("id")): index for index, item in enumerate(programmes) if item.get("id")}
    added = 0
    for record in CANDIDATES:
        position = positions.get(record["id"])
        if position is None:
            positions[record["id"]] = len(programmes)
            programmes.append(record)
            added += 1
        else:
            programmes[position] = record
    write_json(PROGRAMMES_PATH, programmes)

    by_institution = load_json(BY_INSTITUTION_PATH)
    by_institution[SIAC] = SIAC_CANDIDATES
    by_institution[ST_ELIZABETH] = ST_ELIZABETH_CANDIDATES
    write_json(BY_INSTITUTION_PATH, dict(sorted(by_institution.items())))

    summary = load_json(SUMMARY_PATH)
    institution_counts = dict(sorted(Counter(record["institution"] for record in programmes).items()))
    review_counts = dict(sorted(Counter(record.get("review_status") or "needs_admin_review" for record in programmes).items()))
    summary.update({
        "programme_count": len(programmes),
        "institution_count": len(institution_counts),
        "institutions": institution_counts,
        "review_status_counts": review_counts,
        "update_note": "CHE historical candidates and supplied SIAC/St Elizabeth prospectus candidates remain private until current official verification and admin approval.",
    })
    write_json(SUMMARY_PATH, summary)

    audit = load_json(SOURCE_AUDIT_PATH)
    upsert_by_key(audit, "source_path", {
        "institution": SIAC,
        "source_path": SIAC_SOURCE,
        "status": "private_admin_candidate_extract",
        "records_extracted": len(SIAC_CANDIDATES),
        "data_found": ["five programme names", "entry requirements", "durations", "application windows for two programmes", "career opportunities for consumer science programmes", "2025-2026 fee details"],
        "shortage": ["Prospectus is for 2025-2026 and must not be treated as current after its published year.", "No verified current official application link was supplied.", "Programme availability, fees, application dates, and accreditation need current official confirmation before publication."],
    })
    upsert_by_key(audit, "source_path", {
        "institution": ST_ELIZABETH,
        "source_path": ST_ELIZABETH_SOURCE,
        "status": "private_admin_candidate_extract",
        "records_extracted": len(ST_ELIZABETH_CANDIDATES),
        "data_found": ["six programme names", "entry requirements", "programme durations", "NMDS loan bursary note"],
        "shortage": ["Source material has no publication date.", "No fee schedule, official contact details, application link, or accreditation evidence was supplied.", "All programme details require direct college confirmation before publication."],
    })
    write_json(SOURCE_AUDIT_PATH, audit)

    coverage = load_json(COVERAGE_PATH)
    upsert_by_key(coverage, "name", {
        "name": "SIAC prospectus 2025-2026",
        "local_path": SIAC_SOURCE,
        "institution": SIAC,
        "coverage_type": "institution_prospectus_document",
        "status": "private_admin_candidates_only",
        "note": "Five programme candidates and dated fee notes were captured for admin review only. Confirm all current details directly with SIAC before publishing.",
    })
    upsert_by_key(coverage, "name", {
        "name": "St Elizabeth College supplied subject prospectus",
        "local_path": ST_ELIZABETH_SOURCE,
        "institution": ST_ELIZABETH,
        "coverage_type": "supplied_college_prospectus_document",
        "status": "private_admin_candidates_only",
        "note": "Six programme candidates were captured from undated supplied material. Confirm all current details directly with St Elizabeth College before publishing.",
    })
    write_json(COVERAGE_PATH, coverage)

    print(json.dumps({
        "added_candidates": added,
        "programme_count": len(programmes),
        "institution_count": len(institution_counts),
        "review_status_counts": review_counts,
    }, indent=2))


if __name__ == "__main__":
    main()
