from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REAL_DIR = ROOT / "data" / "real"
OUT_FILE = ROOT / "data" / "admin-catalog.js"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def slug(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "item"


def compact_programme(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record.get("id"),
        "institution": record.get("institution"),
        "name": record.get("name"),
        "code": record.get("code"),
        "category": record.get("category"),
        "faculty": record.get("faculty"),
        "level": record.get("level"),
        "duration": record.get("duration"),
        "deliveryMode": record.get("delivery_mode") or record.get("mode"),
        "overview": record.get("overview"),
        "requirementsSummary": record.get("requirements_summary"),
        "careers": record.get("career_options") or [],
        "sourceUrl": record.get("source_url"),
        "sourcePath": record.get("source_path"),
        "supportingSourcePath": record.get("supporting_source_path"),
        "supportingFeeSourcePath": record.get("supporting_fee_source_path"),
        "sourceType": record.get("source_type"),
        "extractionMethod": record.get("extraction_method"),
        "reviewStatus": record.get("review_status", "needs_admin_review"),
        "sourceNote": record.get("source_note"),
    }


def fee_item_type(name: str) -> str:
    lower = name.lower()
    if "application" in lower:
        return "application"
    if "acceptance" in lower or "admission" in lower:
        return "acceptance"
    if "tuition" in lower:
        return "tuition"
    if "boarding" in lower:
        return "boarding"
    if "exam" in lower:
        return "exam"
    if "registration" in lower:
        return "registration"
    return "other"


def flatten_fee_schedule(path: Path) -> dict[str, Any]:
    fee = load_json(path)
    title = fee.get("source_title") or path.stem
    academic_year = fee.get("academic_year")
    schedule_id = f"fee-schedule-{slug(fee.get('institution', 'institution'))}-{slug(title)}-{slug(academic_year or 'unknown')}"
    items: list[dict[str, Any]] = []

    for item in fee.get("fee_items", []):
        for category, amount in [
            ("Local & SADC", item.get("local_sadc_amount")),
            ("International", item.get("international_amount")),
        ]:
            if amount is None:
                continue
            items.append(
                {
                    "id": f"{schedule_id}-{slug(item.get('programme_group', 'tuition'))}-{slug(category)}",
                    "programmeGroup": item.get("programme_group"),
                    "faculty": item.get("faculty"),
                    "name": "Tuition",
                    "type": "tuition",
                    "amount": amount,
                    "studentCategory": category,
                    "basis": "annual",
                }
            )

    for item in fee.get("programme_fee_items", []):
        name = "Tuition levy" if item.get("levy_percent_of_tuition") is not None else "Tuition"
        items.append(
            {
                "id": f"{schedule_id}-{slug(item.get('programme_group', 'fee'))}-{slug(name)}-{len(items) + 1}",
                "programmeGroup": item.get("programme_group"),
                "name": name,
                "type": "levy" if item.get("levy_percent_of_tuition") is not None else "tuition",
                "amount": item.get("tuition_amount"),
                "percentOfTuition": item.get("levy_percent_of_tuition"),
                "studentCategory": item.get("student_category"),
                "attendanceMode": item.get("attendance_mode"),
                "basis": "annual",
            }
        )

    for item in fee.get("programme_component_fee_items", []):
        name = item.get("item", "Fee")
        items.append(
            {
                "id": f"{schedule_id}-{slug(item.get('programme_group', 'fee'))}-{slug(name)}-{len(items) + 1}",
                "programmeGroup": item.get("programme_group"),
                "name": name,
                "type": fee_item_type(name),
                "amount": item.get("amount"),
                "studentCategory": item.get("student_category"),
                "attendanceMode": item.get("attendance_mode"),
                "basis": item.get("basis"),
                "note": item.get("source_note"),
            }
        )

    for item in fee.get("fee_category_items", []):
        name = item.get("item", "Fee")
        for category, amount in [
            ("Local & SADC", item.get("local_sadc_amount")),
            ("International", item.get("international_amount")),
        ]:
            if amount is None:
                continue
            items.append(
                {
                    "id": f"{schedule_id}-{slug(name)}-{slug(category)}-{len(items) + 1}",
                    "programmeGroup": item.get("fee_group"),
                    "name": name,
                    "type": fee_item_type(name),
                    "amount": amount,
                    "studentCategory": category,
                    "basis": item.get("basis"),
                    "note": item.get("source_note"),
                }
            )

    for item in fee.get("other_fees", []) + fee.get("confirmed_fee_items", []):
        name = item.get("item", "Fee")
        items.append(
            {
                "id": f"{schedule_id}-{slug(name)}-{len(items) + 1}",
                "name": name,
                "type": fee_item_type(name),
                "amount": item.get("amount"),
                "basis": item.get("basis"),
                "annualEstimate": item.get("annual_estimate"),
                "refundStatus": item.get("refund_status"),
                "note": item.get("source_note"),
            }
        )

    return {
        "id": schedule_id,
        "institution": fee.get("institution"),
        "title": title,
        "academicYear": academic_year,
        "currency": fee.get("currency", "LSL"),
        "reviewStatus": fee.get("review_status", "needs_admin_review"),
        "sourceUrl": fee.get("source_url"),
        "sourcePath": fee.get("source_path"),
        "notes": fee.get("notes") or [],
        "missingItems": fee.get("missing_fee_items") or [],
        "items": items,
    }


def build_data_gaps(programmes: list[dict[str, Any]], fees: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for programme in programmes:
        if not programme.get("duration"):
            gaps.append(
                {
                    "id": f"gap-{programme['id']}-duration",
                    "type": "duration_missing",
                    "priority": "medium",
                    "status": "open",
                    "institution": programme["institution"],
                    "programmeId": programme["id"],
                    "programmeName": programme["name"],
                    "title": "Missing duration",
                    "description": "Duration was not captured from the current source data.",
                }
            )
        if not programme.get("requirementsSummary"):
            gaps.append(
                {
                    "id": f"gap-{programme['id']}-requirements",
                    "type": "requirements_missing",
                    "priority": "high",
                    "status": "open",
                    "institution": programme["institution"],
                    "programmeId": programme["id"],
                    "programmeName": programme["name"],
                    "title": "Missing entry requirements",
                    "description": "Entry requirements were not captured from the current source data.",
                }
            )
    for schedule in fees:
        for missing in schedule.get("missingItems", []):
            gaps.append(
                {
                    "id": f"gap-{schedule['id']}-{slug(missing)}",
                    "type": "fee_missing",
                    "priority": "medium",
                    "status": "open",
                    "institution": schedule["institution"],
                    "programmeId": None,
                    "programmeName": None,
                    "title": "Missing fee amount",
                    "description": missing,
                }
            )
    return gaps


def institution_review_status(name: str) -> str:
    if name in {"Lesotho College of Education", "Imperial Business College"}:
        return "needs_review"
    return "verified"


def main() -> None:
    summary = load_json(REAL_DIR / "summary.json")
    programmes = [compact_programme(record) for record in load_json(REAL_DIR / "programmes.flat.json")]
    fees = [flatten_fee_schedule(path) for path in sorted((REAL_DIR / "fees").glob("*.json"))]
    source_audit = load_json(REAL_DIR / "source-audit.json")
    gaps = build_data_gaps(programmes, fees)
    institutions = [
        {
            "name": name,
            "programmeCount": count,
            "reviewStatus": institution_review_status(name),
        }
        for name, count in sorted(summary.get("institutions", {}).items())
    ]

    payload = {
        "summary": {
            "programmeCount": len(programmes),
            "institutionCount": len(institutions),
            "sourceCount": len(source_audit),
            "feeScheduleCount": len(fees),
            "feeItemCount": sum(len(schedule["items"]) for schedule in fees),
            "openGapCount": len(gaps),
        },
        "institutions": institutions,
        "programmes": programmes,
        "fees": fees,
        "dataGaps": gaps,
        "sources": source_audit,
    }

    OUT_FILE.write_text(
        "window.EDUGUIDE_ADMIN_DATA = "
        + json.dumps(payload, indent=2, ensure_ascii=True)
        + ";\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    main()
