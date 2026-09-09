from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REAL_DIR = ROOT / "data" / "real"
PROGRAMMES_PATH = REAL_DIR / "programmes.flat.json"
SUMMARY_PATH = REAL_DIR / "summary.json"
SOURCE_AUDIT_PATH = REAL_DIR / "source-audit.json"
COVERAGE_PATH = REAL_DIR / "source-coverage.json"

ACCREDITED_PROGRAMMES_SOURCE = "data/references/che-list-of-accredited-programmes-december-2017.pdf"
HEI_PROFILES_SOURCE = "data/references/che-profiles-of-heis-2017.pdf"
HISTORICAL_NOTE = (
    "Imported from the Council on Higher Education historical programme list dated December 2017. "
    "Its accreditation periods ended by 2023, so this is an admin-review candidate only and must not be "
    "treated as current admission, accreditation, fee, duration, or entry-requirement evidence."
)


def candidate(
    record_id: str,
    institution: str,
    name: str,
    category: str,
    faculty: str,
    level: str,
) -> dict[str, Any]:
    return {
        "id": record_id,
        "institution": institution,
        "name": name,
        "category": category,
        "faculty": faculty,
        "level": level,
        "duration": None,
        "requirements_summary": None,
        "source_url": None,
        "source_path": ACCREDITED_PROGRAMMES_SOURCE,
        "source_type": "official_regulator_historical_pdf",
        "extraction_method": "manual_text_extract",
        "review_status": "needs_admin_review",
        "career_options": [],
        "skill_options": [],
        "source_note": HISTORICAL_NOTE,
    }


CANDIDATES = [
    candidate("nhtc-certificate-auxiliary-social-work-che-2017", "National Health Training College", "Certificate in Auxiliary Social Work", "Health & Medicine", "Health Sciences", "Certificate"),
    candidate("nhtc-certificate-nursing-assistant-che-2017", "National Health Training College", "Certificate in Nursing Assistant", "Health & Medicine", "Health Sciences", "Certificate"),
    candidate("nhtc-diploma-environmental-health-che-2017", "National Health Training College", "Diploma in Environmental Health", "Health & Medicine", "Health Sciences", "Diploma"),
    candidate("nhtc-diploma-general-nursing-che-2017", "National Health Training College", "Diploma in General Nursing", "Health & Medicine", "Health Sciences", "Diploma"),
    candidate("nhtc-diploma-medical-laboratory-sciences-che-2017", "National Health Training College", "Diploma in Medical Laboratory Sciences", "Health & Medicine", "Health Sciences", "Diploma"),
    candidate("nhtc-diploma-midwifery-che-2017", "National Health Training College", "Diploma in Midwifery", "Health & Medicine", "Health Sciences", "Diploma"),
    candidate("nhtc-diploma-primary-health-care-nurse-clinician-che-2017", "National Health Training College", "Diploma in Primary Health Care (Nurse Clinician)", "Health & Medicine", "Health Sciences", "Diploma"),
    candidate("nhtc-diploma-ophthalmic-nursing-che-2017", "National Health Training College", "Diploma in Ophthalmic Nursing", "Health & Medicine", "Health Sciences", "Diploma"),
    candidate("nhtc-diploma-pharmacy-technology-che-2017", "National Health Training College", "Diploma in Pharmacy Technology", "Health & Medicine", "Health Sciences", "Diploma"),
    candidate("nhtc-diploma-psychiatric-mental-health-nursing-che-2017", "National Health Training College", "Diploma in Psychiatric and Mental Health Nursing", "Health & Medicine", "Health Sciences", "Diploma"),
    candidate("nhtc-diploma-dental-therapy-che-2017", "National Health Training College", "Diploma in Dental Therapy", "Health & Medicine", "Health Sciences", "Diploma"),
    candidate("mac-diploma-general-nursing-che-2017", "Maluti Adventist College", "Diploma in General Nursing", "Health & Medicine", "Health Sciences", "Diploma"),
    candidate("mac-diploma-midwifery-che-2017", "Maluti Adventist College", "Diploma in Midwifery", "Health & Medicine", "Health Sciences", "Diploma"),
    candidate("ssn-certificate-nursing-assistant-che-2017", "Scott Hospital School of Nursing", "Certificate in Nursing Assistant", "Health & Medicine", "Health Sciences", "Certificate"),
    candidate("ssn-diploma-general-nursing-che-2017", "Scott Hospital School of Nursing", "Diploma in General Nursing", "Health & Medicine", "Health Sciences", "Diploma"),
    candidate("ssn-diploma-midwifery-che-2017", "Scott Hospital School of Nursing", "Diploma in Midwifery", "Health & Medicine", "Health Sciences", "Diploma"),
    candidate("idm-diploma-human-resource-development-che-2017", "Institute of Development Management", "Diploma in Human Resource and Development", "Business & Management", "Professional Studies", "Diploma"),
    candidate("idm-advanced-diploma-project-management-che-2017", "Institute of Development Management", "Advanced Diploma in Project Management", "Business & Management", "Professional Studies", "Advanced Diploma"),
    candidate("idm-certificate-community-development-che-2017", "Institute of Development Management", "Certificate in Community Development", "Social Work", "Professional Studies", "Certificate"),
    candidate("idm-diploma-community-development-che-2017", "Institute of Development Management", "Diploma in Community Development", "Social Work", "Professional Studies", "Diploma"),
    candidate("idm-diploma-hiv-aids-management-che-2017", "Institute of Development Management", "Diploma in HIV & AIDS Management", "Health & Medicine", "Professional Studies", "Diploma"),
    candidate("idm-diploma-safety-health-che-2017", "Institute of Development Management", "Diploma in Safety and Health", "Health & Medicine", "Professional Studies", "Diploma"),
    candidate("idm-diploma-accounting-business-studies-che-2017", "Institute of Development Management", "Diploma in Accounting and Business Studies", "Business & Management", "Professional Studies", "Diploma"),
    candidate("idm-certificate-computer-engineering-che-2017", "Institute of Development Management", "Certificate in Computer Engineering", "Technology & IT", "Professional Studies", "Certificate"),
    candidate("idm-diploma-computer-engineering-che-2017", "Institute of Development Management", "Diploma in Computer Engineering", "Technology & IT", "Professional Studies", "Diploma"),
    candidate("idm-diploma-logistics-transport-che-2017", "Institute of Development Management", "Diploma in Logistics and Transport", "Business & Management", "Professional Studies", "Diploma"),
    candidate("idm-cips-programme-che-2017", "Institute of Development Management", "Chartered Institute of Purchasing and Supply (CIPS) Programme", "Business & Management", "Professional Studies", "Professional Programme"),
    candidate("lipam-diploma-public-administration-management-che-2017", "Lesotho Institute of Public Administration and Management", "Diploma in Public Administration and Management", "Law & Government", "Public Administration", "Diploma"),
    candidate("lipam-diploma-human-resources-labour-laws-che-2017", "Lesotho Institute of Public Administration and Management", "Diploma in Human Resources Management and Labour Laws", "Law & Government", "Public Administration", "Diploma"),
    candidate("leboha-family-medicine-specialty-training-che-2017", "Lesotho Boston Health Alliance (LeBoHA)", "Family Medicine Specialty Training Programme", "Health & Medicine", "Health Sciences", "Postgraduate Training"),
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def best_record(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left_score = len(str(left.get("requirements_summary") or "")) + len(str(left.get("overview") or ""))
    right_score = len(str(right.get("requirements_summary") or "")) + len(str(right.get("overview") or ""))
    return right if right_score > left_score else left


def upsert_by_key(items: list[dict[str, Any]], key: str, value: dict[str, Any]) -> None:
    for index, item in enumerate(items):
        if item.get(key) == value.get(key):
            items[index] = value
            return
    items.append(value)


def main() -> None:
    existing = load_json(PROGRAMMES_PATH)
    deduped: list[dict[str, Any]] = []
    positions: dict[str, int] = {}
    duplicates_removed = 0
    for record in existing:
        record_id = str(record.get("id") or "").strip()
        if not record_id:
            continue
        if record_id in positions:
            deduped[positions[record_id]] = best_record(deduped[positions[record_id]], record)
            duplicates_removed += 1
        else:
            positions[record_id] = len(deduped)
            deduped.append(record)

    added = 0
    for record in CANDIDATES:
        if record["id"] not in positions:
            positions[record["id"]] = len(deduped)
            deduped.append(record)
            added += 1
    write_json(PROGRAMMES_PATH, deduped)

    summary = load_json(SUMMARY_PATH)
    institution_counts = dict(sorted(Counter(record["institution"] for record in deduped).items()))
    review_counts = dict(sorted(Counter(record.get("review_status") or "needs_admin_review" for record in deduped).items()))
    summary.update({
        "programme_count": len(deduped),
        "institution_count": len(institution_counts),
        "institutions": institution_counts,
        "review_status_counts": review_counts,
        "update_note": "CHE 2017 historical candidates imported to the private admin-review queue; they require current institution/CHE verification before publication.",
    })
    write_json(SUMMARY_PATH, summary)

    audit = load_json(SOURCE_AUDIT_PATH)
    upsert_by_key(audit, "source_path", {
        "institution": "Council on Higher Education (CHE)",
        "source_path": ACCREDITED_PROGRAMMES_SOURCE,
        "status": "historical_candidate_import",
        "records_extracted": len(CANDIDATES),
        "data_found": ["programme names", "institution names", "historical accreditation decisions", "historical validity periods"],
        "shortage": ["Document is dated December 2017 and its listed validity periods ended by 2023.", "No current entry requirements, programme durations, fees, intake status, or application routes were imported.", "All imported records remain private until current official verification."],
    })
    upsert_by_key(audit, "source_path", {
        "institution": "Council on Higher Education (CHE)",
        "source_path": HEI_PROFILES_SOURCE,
        "status": "historical_context_reference",
        "records_extracted": 0,
        "data_found": ["2016/17 institution locations", "historical programme lists", "historical institutional profiles"],
        "shortage": ["Document is a 2017 profile and is retained only to cross-check historical institution and programme names.", "Do not use it as current admissions, fee, accreditation, or programme-availability evidence."],
    })
    upsert_by_key(audit, "source_url", {
        "institution": "Lesotho higher education sector",
        "source_url": "https://lten.org.ls/blog/a-complete-guide-to-higher-education-institutions-in-lesotho",
        "status": "current_context_reference",
        "records_extracted": 0,
        "data_found": ["2026 higher-education landscape overview", "institution context", "official institution links"],
        "shortage": ["LTEN is a sector guide, not the canonical source for requirements, fees, applications, or accreditation decisions."],
    })
    write_json(SOURCE_AUDIT_PATH, audit)

    coverage = load_json(COVERAGE_PATH)
    upsert_by_key(coverage, "name", {
        "name": "CHE list of accredited programmes (December 2017)",
        "local_path": ACCREDITED_PROGRAMMES_SOURCE,
        "institution": None,
        "coverage_type": "historical_regulator_programme_list",
        "status": "private_admin_candidates_only",
        "note": "Historical CHE programme names were imported into the admin-review queue only. Validity periods in the document ended by 2023 and require current verification before publication.",
    })
    upsert_by_key(coverage, "name", {
        "name": "CHE profiles of higher education institutions (2017)",
        "local_path": HEI_PROFILES_SOURCE,
        "institution": None,
        "coverage_type": "historical_regulator_institution_profiles",
        "status": "historical_context_only",
        "note": "Used to cross-check historical institution names, locations, and programme lists; not current admissions or accreditation evidence.",
    })
    upsert_by_key(coverage, "name", {
        "name": "LTEN higher education institutions guide (2026)",
        "url": "https://lten.org.ls/blog/a-complete-guide-to-higher-education-institutions-in-lesotho",
        "institution": None,
        "coverage_type": "sector_context_and_official_link_discovery",
        "status": "current_context_reference",
        "note": "Useful current landscape context and official-link discovery. Institution pages and regulator sources remain required for programme facts.",
    })
    write_json(COVERAGE_PATH, coverage)

    print(json.dumps({
        "added_candidates": added,
        "duplicate_records_removed": duplicates_removed,
        "programme_count": len(deduped),
        "institution_count": len(institution_counts),
        "review_status_counts": review_counts,
    }, indent=2))


if __name__ == "__main__":
    main()
