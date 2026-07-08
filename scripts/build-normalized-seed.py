from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REAL_DIR = ROOT / "data" / "real"
OUT_FILE = ROOT / "supabase" / "seed.normalized.sql"


INSTITUTION_META = {
    "National University of Lesotho": {"short_name": "NUL", "type": "university", "district": "Maseru", "website": "https://nul.ls/"},
    "NUL Institute of Extra Mural Studies (IEMS)": {"short_name": "IEMS", "type": "institute", "district": "Maseru", "website": "https://nul.ls/iems-2/"},
    "Limkokwing University Lesotho": {"short_name": "LUCT", "type": "university", "district": "Maseru", "website": "https://www.portal.co.ls/apply/courses"},
    "Botho University Lesotho": {"short_name": "Botho", "type": "university", "district": "Maseru", "website": "https://www.bothouniversity.com/lesotho/programmes"},
    "Lerotholi Polytechnic": {"short_name": "LP", "type": "polytechnic", "district": "Maseru", "website": "https://www.lp.ac.ls/"},
    "Lesotho Agricultural College": {"short_name": "LAC", "type": "college", "district": "Maseru", "website": "https://lac.org.ls/"},
    "Lesotho College of Education": {"short_name": "LCE", "type": "college", "district": None, "website": None},
    "Roma College of Nursing": {"short_name": "RCN", "type": "college", "district": "Maseru", "website": "https://www.che.ac.ls/roma-college-of-nursing-rcn-accredited-programmes/"},
    "Paray School of Nursing": {"short_name": "Paray", "type": "college", "district": "Thaba-Tseka", "website": "https://www.parayson.ac.ls/"},
    "Centre for Accounting Studies": {"short_name": "CAS", "type": "college", "district": "Maseru", "website": "https://cas.ac.ls/"},
    "Imperial Business College": {"short_name": "IBC", "type": "international_college", "district": "Kathmandu, Nepal", "website": "https://www.imperialcollege.edu.np/", "country": "Nepal", "verification_status": "needs_review"},
}

SUBJECTS = [
    ("MATH", "Mathematics", "Core"),
    ("ENG", "English", "Core"),
    ("SES", "Sesotho", "Language"),
    ("PSCI", "Physical Science", "Science"),
    ("ACC", "Accounting", "Business"),
    ("BIO", "Biology", "Science"),
    ("AGR", "Agriculture", "Agriculture"),
    ("HIST", "History", "Humanities"),
    ("GEO", "Geography", "Humanities"),
    ("PHY", "Physics", "Science"),
    ("CHEM", "Chemistry", "Science"),
    ("ECON", "Economics", "Business"),
    ("LIT", "English Literature", "Humanities"),
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def slug(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "item"


def q(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def jq(value: Any) -> str:
    return q(json.dumps(value, ensure_ascii=True, sort_keys=True))


def maybe_num(value: Any) -> str:
    if value is None:
        return "null"
    return str(value)


def institution_id(name: str) -> str:
    return f"(select id from public.institutions where name = {q(name)} limit 1)"


def faculty_id(institution: str, faculty: str | None) -> str:
    if not faculty:
        return "null"
    return (
        "(select f.id from public.faculties f "
        f"join public.institutions i on i.id = f.institution_id where i.name = {q(institution)} "
        f"and f.name = {q(faculty)} limit 1)"
    )


def programme_id(external_key: str) -> str:
    return f"(select id from public.programmes where external_key = {q(external_key)} limit 1)"


def source_condition(url: str | None, local_path: str | None) -> str:
    parts = []
    if url:
        parts.append(f"url = {q(url)}")
    if local_path:
        parts.append(f"local_path = {q(local_path)}")
    return " or ".join(parts) or "false"


def source_id(url: str | None, local_path: str | None) -> str:
    return f"(select id from public.source_documents where {source_condition(url, local_path)} limit 1)"


def trust_level(source_type: str | None, url: str | None, local_path: str | None, extraction_method: str | None) -> str:
    text = " ".join([source_type or "", url or "", local_path or "", extraction_method or ""]).lower()
    if "manual_user_confirmation" in text:
        return "manual_confirmation"
    if "international_prospectus" in text or "visual_pdf_review" in text:
        return "unverified"
    if local_path:
        return "official_local"
    if "third_party" in text or "scribd" in text or "mabumbe" in text:
        return "third_party"
    if any(domain in text for domain in ["nul.ls", "portal.co.ls", "bothouniversity.com", "lp.ac.ls", "che.ac.ls", "cas.ac.ls", "lac.org.ls", "gov.ls", "finance.gov.ls"]):
        return "verified_core"
    return "unverified"


def title_from_source(institution: str, source_type: str | None, url: str | None, local_path: str | None) -> str:
    if local_path:
        return Path(local_path).name
    if url:
        return f"{institution} - {source_type or 'source'}"
    return f"{institution} - source"


def add_source(
    sources: dict[tuple[str | None, str | None], dict[str, Any]],
    institution: str,
    source_type: str | None,
    url: str | None,
    local_path: str | None,
    extraction_method: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    if not url and not local_path:
        return
    key = (url, local_path)
    sources.setdefault(
        key,
        {
            "institution": institution,
            "name": title_from_source(institution, source_type, url, local_path),
            "source_type": source_type or "source",
            "url": url,
            "local_path": local_path,
            "trust_level": trust_level(source_type, url, local_path, extraction_method),
            "extraction_method": extraction_method,
            "metadata": metadata or {},
        },
    )


def fee_type(name: str) -> str:
    lower = name.lower()
    if "application" in lower:
        return "application"
    if "acceptance" in lower or "admission" in lower:
        return "acceptance"
    if "tuition" in lower:
        return "tuition"
    if "levy" in lower:
        return "levy"
    if "boarding" in lower:
        return "boarding"
    if "catering" in lower:
        return "catering"
    if "exam" in lower:
        return "exam"
    if "book" in lower:
        return "book"
    if "registration" in lower:
        return "registration"
    if "subscription" in lower:
        return "professional_body"
    return "other"


def insert_source_sql(doc: dict[str, Any]) -> str:
    return (
        "insert into public.source_documents "
        "(name, source_type, url, local_path, owner_institution_id, trust_level, extraction_method, metadata)\n"
        "select "
        f"{q(doc['name'])}, {q(doc['source_type'])}, {q(doc['url'])}, {q(doc['local_path'])}, "
        f"{institution_id(doc['institution'])}, {q(doc['trust_level'])}, {q(doc['extraction_method'])}, {jq(doc['metadata'])}::jsonb\n"
        f"where not exists (select 1 from public.source_documents where {source_condition(doc['url'], doc['local_path'])});"
    )


def main() -> None:
    programmes = load_json(REAL_DIR / "programmes.flat.json")
    fee_files = sorted((REAL_DIR / "fees").glob("*.json"))
    handbook_files = sorted((REAL_DIR / "handbooks").glob("*.json"))
    fees = [load_json(path) for path in fee_files]
    handbooks = [load_json(path) for path in handbook_files]

    institutions = sorted({p["institution"] for p in programmes} | {f["institution"] for f in fees} | {h["institution"] for h in handbooks})
    faculties: set[tuple[str, str]] = set()
    sources: dict[tuple[str | None, str | None], dict[str, Any]] = {}

    for programme in programmes:
        institution = programme["institution"]
        if programme.get("faculty"):
            faculties.add((institution, programme["faculty"]))
        add_source(sources, institution, programme.get("source_type"), programme.get("source_url"), programme.get("source_path"), programme.get("extraction_method"))
        add_source(sources, institution, "supporting_source", None, programme.get("supporting_source_path"), programme.get("extraction_method"))
        add_source(sources, institution, "fee_supporting_source", None, programme.get("supporting_fee_source_path"), programme.get("extraction_method"))

    for fee in fees:
        institution = fee["institution"]
        add_source(sources, institution, "fee_schedule", fee.get("source_url"), fee.get("source_path"), fee.get("extraction_method"), {"source_title": fee.get("source_title")})
        add_source(sources, institution, "supporting_fee_source", None, fee.get("supporting_source_path"), fee.get("extraction_method"))
        for item in fee.get("fee_items", []):
            if item.get("faculty"):
                faculties.add((institution, item["faculty"]))

    for handbook in handbooks:
        add_source(sources, handbook["institution"], "student_handbook", None, handbook.get("source_path"), handbook.get("extraction_method"), {"source_title": handbook.get("source_title")})

    lines: list[str] = []
    lines.append("-- Generated by scripts/build-normalized-seed.py")
    lines.append("-- Loads source-derived EduGuide LS catalogue data into the normalized schema.")
    lines.append("begin;")
    lines.append("")

    lines.append("insert into public.import_batches (batch_key, source_label, import_method, completed_at, metadata)")
    lines.append(
        "values ("
        f"{q('real-catalogue-2026-06-08')}, {q('EduGuide LS real catalogue')}, "
        f"{q('json_to_normalized_sql')}, now(), "
        f"{jq({'programme_count': len(programmes), 'institution_count': len(institutions)})}::jsonb)"
    )
    lines.append("on conflict (batch_key) do update set completed_at = excluded.completed_at, metadata = excluded.metadata;")
    lines.append("")

    for code, name, group in SUBJECTS:
        lines.append(
            "insert into public.subjects (code, name, subject_group) "
            f"values ({q(code)}, {q(name)}, {q(group)}) "
            "on conflict (code) do update set name = excluded.name, subject_group = excluded.subject_group;"
        )
    lines.append("")

    for institution in institutions:
        meta = INSTITUTION_META.get(institution, {})
        verification_status = meta.get("verification_status") or ("verified" if meta.get("website") else "needs_review")
        lines.append(
            "insert into public.institutions (name, short_name, institution_type, district, website_url, verification_status, metadata) "
            f"values ({q(institution)}, {q(meta.get('short_name'))}, {q(meta.get('type'))}, {q(meta.get('district'))}, {q(meta.get('website'))}, "
            f"{q(verification_status)}, {jq(meta)}::jsonb) "
            "on conflict (name) do update set short_name = excluded.short_name, institution_type = excluded.institution_type, "
            "district = excluded.district, website_url = excluded.website_url, verification_status = excluded.verification_status, metadata = excluded.metadata;"
        )
        if meta.get("short_name"):
            lines.append(
                "insert into public.institution_aliases (institution_id, alias, alias_type) "
                f"values ({institution_id(institution)}, {q(meta['short_name'])}, 'short_name') "
                "on conflict (institution_id, alias) do update set alias_type = excluded.alias_type;"
            )
    lines.append("")

    for institution, faculty in sorted(faculties):
        lines.append(
            "insert into public.faculties (institution_id, name, external_key) "
            f"values ({institution_id(institution)}, {q(faculty)}, {q(slug(institution + '-' + faculty))}) "
            "on conflict (institution_id, name) do update set external_key = excluded.external_key;"
        )
    lines.append("")

    for doc in sorted(sources.values(), key=lambda item: (item["institution"], item["name"])):
        lines.append(insert_source_sql(doc))
    lines.append("")

    for programme in programmes:
        external_key = programme["id"]
        institution = programme["institution"]
        source_expr = source_id(programme.get("source_url"), programme.get("source_path")) if (programme.get("source_url") or programme.get("source_path")) else "null"
        lines.append(
            "insert into public.programmes "
            "(external_key, institution_id, faculty_id, code, name, category, qualification_level, duration_text, delivery_mode, overview, review_status, raw_payload) "
            f"values ({q(external_key)}, {institution_id(institution)}, {faculty_id(institution, programme.get('faculty'))}, "
            f"{q(programme.get('code'))}, {q(programme.get('name'))}, {q(programme.get('category'))}, {q(programme.get('level'))}, "
            f"{q(programme.get('duration'))}, {q(programme.get('delivery_mode') or programme.get('mode'))}, {q(programme.get('overview'))}, "
            f"{q(programme.get('review_status', 'needs_admin_review'))}, {jq(programme)}::jsonb) "
            "on conflict (external_key) do update set institution_id = excluded.institution_id, faculty_id = excluded.faculty_id, "
            "code = excluded.code, name = excluded.name, category = excluded.category, qualification_level = excluded.qualification_level, "
            "duration_text = excluded.duration_text, delivery_mode = excluded.delivery_mode, overview = excluded.overview, "
            "review_status = excluded.review_status, raw_payload = excluded.raw_payload;"
        )
        if source_expr != "null":
            lines.append(
                "insert into public.programme_sources "
                "(programme_id, source_document_id, relation_type, extraction_method, evidence_text) "
                f"values ({programme_id(external_key)}, {source_expr}, 'primary', {q(programme.get('extraction_method'))}, {q(programme.get('requirements_summary') or programme.get('overview'))}) "
                "on conflict (programme_id, source_document_id, relation_type) do update set extraction_method = excluded.extraction_method, evidence_text = excluded.evidence_text;"
            )
        if programme.get("supporting_source_path"):
            lines.append(
                "insert into public.programme_sources "
                "(programme_id, source_document_id, relation_type, extraction_method) "
                f"values ({programme_id(external_key)}, {source_id(None, programme.get('supporting_source_path'))}, 'supporting', {q(programme.get('extraction_method'))}) "
                "on conflict (programme_id, source_document_id, relation_type) do update set extraction_method = excluded.extraction_method;"
            )
        if programme.get("supporting_fee_source_path"):
            lines.append(
                "insert into public.programme_sources "
                "(programme_id, source_document_id, relation_type, extraction_method) "
                f"values ({programme_id(external_key)}, {source_id(None, programme.get('supporting_fee_source_path'))}, 'fee_supporting', {q(programme.get('extraction_method'))}) "
                "on conflict (programme_id, source_document_id, relation_type) do update set extraction_method = excluded.extraction_method;"
            )
        if programme.get("requirements_summary"):
            lines.append(
                "insert into public.programme_requirement_sets "
                "(programme_id, route_name, requirement_summary, source_document_id, review_status, raw_payload) "
                f"values ({programme_id(external_key)}, 'General entry', {q(programme.get('requirements_summary'))}, {source_expr}, "
                f"{q(programme.get('review_status', 'needs_admin_review'))}, {jq({'source_field': 'requirements_summary'})}::jsonb) "
                "on conflict (programme_id, route_name) do update set requirement_summary = excluded.requirement_summary, "
                "source_document_id = excluded.source_document_id, review_status = excluded.review_status, raw_payload = excluded.raw_payload;"
            )
        for career in programme.get("career_options", []) or []:
            career_key = career.strip()
            if not career_key:
                continue
            lines.append(
                "insert into public.careers (name, review_status) "
                f"values ({q(career_key)}, 'needs_admin_review') "
                "on conflict (name) do update set review_status = excluded.review_status;"
            )
            lines.append(
                "insert into public.programme_careers (programme_id, career_id, relevance_score, mapping_method, review_status) "
                f"values ({programme_id(external_key)}, (select id from public.careers where name = {q(career_key)} limit 1), 90, 'source_pdf', 'needs_admin_review') "
                "on conflict (programme_id, career_id) do update set relevance_score = excluded.relevance_score, mapping_method = excluded.mapping_method;"
            )
        if not programme.get("duration"):
            gap_key = f"gap-{external_key}-duration"
            lines.append(
                "insert into public.data_gaps (external_key, institution_id, programme_id, gap_type, title, description, priority, raw_payload) "
                f"values ({q(gap_key)}, {institution_id(institution)}, {programme_id(external_key)}, 'duration_missing', "
                f"{q('Missing programme duration')}, {q('Duration was not captured from the current source data.')}, 'medium', {jq({'programme': programme.get('name')})}::jsonb) "
                "on conflict (external_key) do update set description = excluded.description, raw_payload = excluded.raw_payload;"
            )
        if not programme.get("requirements_summary"):
            gap_key = f"gap-{external_key}-requirements"
            lines.append(
                "insert into public.data_gaps (external_key, institution_id, programme_id, gap_type, title, description, priority, raw_payload) "
                f"values ({q(gap_key)}, {institution_id(institution)}, {programme_id(external_key)}, 'requirements_missing', "
                f"{q('Missing entry requirements')}, {q('Entry requirements were not captured from the current source data.')}, 'high', {jq({'programme': programme.get('name')})}::jsonb) "
                "on conflict (external_key) do update set description = excluded.description, raw_payload = excluded.raw_payload;"
            )
    lines.append("")

    for fee in fees:
        institution = fee["institution"]
        title = fee.get("source_title") or f"{institution} fee schedule"
        academic_year = fee.get("academic_year")
        schedule_key = f"fee-schedule-{slug(institution)}-{slug(title)}-{slug(academic_year or 'unknown')}"
        src = source_id(fee.get("source_url"), fee.get("source_path")) if (fee.get("source_url") or fee.get("source_path")) else "null"
        lines.append(
            "insert into public.fee_schedules (external_key, institution_id, source_document_id, title, academic_year, currency, review_status, notes, raw_payload) "
            f"values ({q(schedule_key)}, {institution_id(institution)}, {src}, {q(title)}, {q(academic_year)}, {q(fee.get('currency', 'LSL'))}, "
            f"{q(fee.get('review_status', 'needs_admin_review'))}, {q('; '.join(fee.get('notes', [])))}, {jq(fee)}::jsonb) "
            "on conflict (external_key) do update set source_document_id = excluded.source_document_id, title = excluded.title, academic_year = excluded.academic_year, "
            "currency = excluded.currency, review_status = excluded.review_status, notes = excluded.notes, raw_payload = excluded.raw_payload;"
        )

        item_index = 0
        for item in fee.get("fee_items", []):
            for category, amount in [("Local & SADC", item.get("local_sadc_amount")), ("International", item.get("international_amount"))]:
                if amount is None:
                    continue
                item_index += 1
                item_key = f"{schedule_key}-item-{item_index}-{slug(item.get('programme_group', 'fee'))}-{slug(category)}"
                lines.append(
                    "insert into public.fee_items "
                    "(external_key, fee_schedule_id, faculty_id, programme_group, item_name, item_type, amount, student_category, source_document_id, raw_payload) "
                    f"values ({q(item_key)}, (select id from public.fee_schedules where external_key = {q(schedule_key)} limit 1), "
                    f"{faculty_id(institution, item.get('faculty'))}, {q(item.get('programme_group'))}, 'Tuition', 'tuition', {maybe_num(amount)}, {q(category)}, {src}, {jq(item)}::jsonb) "
                    "on conflict (external_key) do update set amount = excluded.amount, raw_payload = excluded.raw_payload;"
                )

        for item in fee.get("programme_fee_items", []):
            item_index += 1
            item_name = "Tuition levy" if item.get("levy_percent_of_tuition") is not None else "Tuition"
            item_key = f"{schedule_key}-item-{item_index}-{slug(item.get('programme_group', 'fee'))}-{slug(item_name)}"
            lines.append(
                "insert into public.fee_items "
                "(external_key, fee_schedule_id, programme_group, item_name, item_type, amount, percent_of_tuition, student_category, attendance_mode, source_document_id, raw_payload) "
                f"values ({q(item_key)}, (select id from public.fee_schedules where external_key = {q(schedule_key)} limit 1), "
                f"{q(item.get('programme_group'))}, {q(item_name)}, {q('levy' if item.get('levy_percent_of_tuition') is not None else 'tuition')}, "
                f"{maybe_num(item.get('tuition_amount'))}, {maybe_num(item.get('levy_percent_of_tuition'))}, {q(item.get('student_category'))}, {q(item.get('attendance_mode'))}, {src}, {jq(item)}::jsonb) "
                "on conflict (external_key) do update set amount = excluded.amount, percent_of_tuition = excluded.percent_of_tuition, raw_payload = excluded.raw_payload;"
            )

        for item in fee.get("programme_component_fee_items", []):
            item_index += 1
            item_name = item.get("item", "Fee")
            item_key = f"{schedule_key}-item-{item_index}-{slug(item.get('programme_group', 'fee'))}-{slug(item_name)}"
            lines.append(
                "insert into public.fee_items "
                "(external_key, fee_schedule_id, programme_group, item_name, item_type, amount, basis, student_category, attendance_mode, source_document_id, notes, raw_payload) "
                f"values ({q(item_key)}, (select id from public.fee_schedules where external_key = {q(schedule_key)} limit 1), "
                f"{q(item.get('programme_group'))}, {q(item_name)}, {q(fee_type(item_name))}, {maybe_num(item.get('amount'))}, "
                f"{q(item.get('basis'))}, {q(item.get('student_category'))}, {q(item.get('attendance_mode'))}, {src}, "
                f"{q(item.get('source_note'))}, {jq(item)}::jsonb) "
                "on conflict (external_key) do update set amount = excluded.amount, basis = excluded.basis, raw_payload = excluded.raw_payload;"
            )

        for item in fee.get("fee_category_items", []):
            item_name = item.get("item", "Fee")
            for category, amount in [("Local & SADC", item.get("local_sadc_amount")), ("International", item.get("international_amount"))]:
                if amount is None:
                    continue
                item_index += 1
                item_key = f"{schedule_key}-item-{item_index}-{slug(item_name)}-{slug(category)}"
                lines.append(
                    "insert into public.fee_items "
                    "(external_key, fee_schedule_id, programme_group, item_name, item_type, amount, basis, student_category, source_document_id, notes, raw_payload) "
                    f"values ({q(item_key)}, (select id from public.fee_schedules where external_key = {q(schedule_key)} limit 1), "
                    f"{q(item.get('fee_group'))}, {q(item_name)}, {q(fee_type(item_name))}, {maybe_num(amount)}, "
                    f"{q(item.get('basis'))}, {q(category)}, {src}, {q(item.get('source_note'))}, {jq(item)}::jsonb) "
                    "on conflict (external_key) do update set amount = excluded.amount, basis = excluded.basis, raw_payload = excluded.raw_payload;"
                )

        for item in fee.get("other_fees", []) + fee.get("confirmed_fee_items", []):
            item_index += 1
            item_key = f"{schedule_key}-item-{item_index}-{slug(item.get('item', 'fee'))}"
            lines.append(
                "insert into public.fee_items "
                "(external_key, fee_schedule_id, item_name, item_type, amount, basis, refund_status, annual_estimate_amount, source_document_id, notes, raw_payload) "
                f"values ({q(item_key)}, (select id from public.fee_schedules where external_key = {q(schedule_key)} limit 1), "
                f"{q(item.get('item'))}, {q(fee_type(item.get('item', 'fee')))}, {maybe_num(item.get('amount'))}, {q(item.get('basis'))}, "
                f"{q(item.get('refund_status'))}, {maybe_num(item.get('annual_estimate'))}, {src}, {q(item.get('source_note'))}, {jq(item)}::jsonb) "
                "on conflict (external_key) do update set amount = excluded.amount, basis = excluded.basis, refund_status = excluded.refund_status, raw_payload = excluded.raw_payload;"
            )

        for missing in fee.get("missing_fee_items", []):
            gap_key = f"gap-{schedule_key}-{slug(missing)}"
            lines.append(
                "insert into public.data_gaps (external_key, institution_id, source_document_id, gap_type, title, description, priority, raw_payload) "
                f"values ({q(gap_key)}, {institution_id(institution)}, {src}, 'fee_missing', {q('Missing fee amount')}, "
                f"{q(missing)}, 'medium', {jq({'fee_schedule': title})}::jsonb) "
                "on conflict (external_key) do update set description = excluded.description, source_document_id = excluded.source_document_id;"
            )
    lines.append("")

    for handbook in handbooks:
        institution = handbook["institution"]
        src = source_id(None, handbook.get("source_path"))
        policies: list[tuple[str, str, str, Any]] = []
        for index, rule in enumerate(handbook.get("progression_rules", []), start=1):
            policies.append(("progression", f"Progression rule {index}", rule, {"rule": rule}))
        for index, rule in enumerate(handbook.get("registration_rules", []), start=1):
            policies.append(("registration", f"Registration rule {index}", rule, {"rule": rule}))
        if handbook.get("fees_policy"):
            policies.append(("fees", "Fees policy", json.dumps(handbook["fees_policy"], ensure_ascii=True), handbook["fees_policy"]))
        if handbook.get("campus_services"):
            policies.append(("campus_services", "Campus services", json.dumps(handbook["campus_services"], ensure_ascii=True), handbook["campus_services"]))
        if handbook.get("graduation"):
            policies.append(("graduation", "Graduation schedule", json.dumps(handbook["graduation"], ensure_ascii=True), handbook["graduation"]))
        for policy_type, title, text, payload in policies:
            key = f"policy-{slug(institution)}-{slug(policy_type)}-{slug(title)}"
            lines.append(
                "insert into public.institution_policies (external_key, institution_id, source_document_id, policy_type, title, policy_text, raw_payload) "
                f"values ({q(key)}, {institution_id(institution)}, {src}, {q(policy_type)}, {q(title)}, {q(text)}, {jq(payload)}::jsonb) "
                "on conflict (external_key) do update set policy_text = excluded.policy_text, raw_payload = excluded.raw_payload;"
            )

    nmds_url = "https://www.gov.ls/eservice/ministry-of-finance-and-development-planning-23/"
    lines.append("")
    lines.append(
        "insert into public.source_documents (name, source_type, url, owner_institution_id, trust_level, extraction_method, metadata)\n"
        f"select 'NMDS Government Bursary Service', 'government_service', {q(nmds_url)}, null, 'verified_core', 'manual_public_source', "
        f"{jq({'provider': 'National Manpower Development Secretariat'})}::jsonb\n"
        f"where not exists (select 1 from public.source_documents where url = {q(nmds_url)});"
    )
    lines.append(
        "insert into public.scholarships (name, provider, description, eligibility_summary, source_document_id, source_url, review_status, status) "
        "values ("
        f"{q('NMDS Sponsorship/Bursary')}, {q('National Manpower Development Secretariat')}, "
        f"{q('Government sponsorship pathway for eligible Lesotho students.')}, "
        f"{q('Eligibility depends on academic, programme, application, and background factors. EduGuide LS can estimate readiness, but final approval is made by NMDS.')}, "
        f"{source_id(nmds_url, None)}, {q(nmds_url)}, 'approved', 'approved') "
        "on conflict (provider, name) do update set description = excluded.description, eligibility_summary = excluded.eligibility_summary, "
        "source_document_id = excluded.source_document_id, source_url = excluded.source_url, review_status = excluded.review_status, status = excluded.status;"
    )
    criteria = [
        ("academic_performance", "Academic performance", 40, "Grades and subject performance matter for sponsorship readiness."),
        ("programme_priority", "Programme priority and relevance", 25, "The selected programme should be relevant and sponsorable."),
        ("financial_background", "Financial/background need", 20, "Student background and ability to self-fund should be considered where data is available."),
        ("documentation_readiness", "Documentation readiness", 15, "Applications should have required documents and complete profile information."),
    ]
    for key, label, weight, summary in criteria:
        lines.append(
            "insert into public.scholarship_criteria (scholarship_id, criterion_key, criterion_label, criterion_type, weight, rule_summary) "
            "values ("
            f"(select id from public.scholarships where provider = {q('National Manpower Development Secretariat')} and name = {q('NMDS Sponsorship/Bursary')} limit 1), "
            f"{q(key)}, {q(label)}, 'score_component', {weight}, {q(summary)}) "
            "on conflict (scholarship_id, criterion_key) do update set criterion_label = excluded.criterion_label, "
            "criterion_type = excluded.criterion_type, weight = excluded.weight, rule_summary = excluded.rule_summary;"
        )

    lines.append("")
    lines.append("commit;")

    OUT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(OUT_FILE),
                "institutions": len(institutions),
                "faculties": len(faculties),
                "programmes": len(programmes),
                "sources": len(sources),
                "fee_schedules": len(fees),
                "handbooks": len(handbooks),
                "sql_lines": len(lines),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
