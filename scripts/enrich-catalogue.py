from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REAL_DIR = ROOT / "data" / "real"
PROGRAMMES_FILE = REAL_DIR / "programmes.flat.json"


SPECIFIC_CAREER_RULES: list[tuple[tuple[str, ...], list[str]]] = [
    (("business information technology", "business it"), ["Business Systems Analyst", "IT Business Analyst", "Systems Administrator", "Technology Project Officer"]),
    (("digital film", "film production", "film and television"), ["Film Producer", "Director", "Video Editor", "Cinematographer"]),
    (("professional communication", "public relations"), ["Communications Officer", "Public Relations Officer", "Corporate Communications Specialist", "Content Strategist"]),
    (("network security", "cyber security", "cybersecurity", "computer forensics"), ["Cybersecurity Analyst", "Digital Forensics Investigator", "Security Engineer", "Network Security Specialist"]),
    (("data science", "data analytics"), ["Data Scientist", "Data Analyst", "Machine Learning Engineer", "Business Intelligence Analyst"]),
    (("software engineering",), ["Software Engineer", "Software Developer", "Systems Architect", "Quality Assurance Engineer"]),
    (("electrical engineering", "electronics and communication", "electronics engineering"), ["Electrical Engineer", "Electronics Engineer", "Telecommunications Engineer", "Control Systems Engineer"]),
    (("accounting", "finance", "investment and banking"), ["Accountant", "Auditor", "Financial Analyst", "Banking Officer"]),
    (("nursing", "midwifery", "nursing assistant"), ["Registered Nurse", "Community Health Nurse", "Clinical Nurse", "Nursing Specialist"]),
]

CAREER_RULES: list[tuple[tuple[str, ...], list[str]]] = [
    (("fashion", "textile", "retailing"), ["Fashion Designer", "Textile Designer", "Fashion Buyer", "Retail Manager"]),
    (("architect", "built environment", "construction"), ["Architect", "Architectural Technologist", "Quantity Surveyor", "Urban Planner"]),
    (("broadcast", "journalism", "film", "television", "media", "communication"), ["Journalist", "Broadcast Producer", "Content Producer", "Public Relations Officer"]),
    (("human resource", "hr management"), ["Human Resources Officer", "Talent Acquisition Specialist", "Training Coordinator", "Employee Relations Officer"]),
    (("entrepreneur", "business administration", "business management", "commerce"), ["Business Analyst", "Operations Manager", "Business Development Officer", "Entrepreneur"]),
    (("accounting", "finance", "investment", "banking", "risk management"), ["Accountant", "Auditor", "Financial Analyst", "Banking Officer"]),
    (("hospitality", "tourism", "hotel"), ["Hotel Manager", "Events Coordinator", "Tourism Officer", "Hospitality Manager"]),
    (("data science", "data analytics"), ["Data Scientist", "Data Analyst", "Machine Learning Engineer", "Business Intelligence Analyst"]),
    (("cyber", "network security", "computer forensics"), ["Cybersecurity Analyst", "Digital Forensics Investigator", "Security Engineer", "Network Security Specialist"]),
    (("software", "computing", "computer science", "information technology", "business information technology", "mobile computing"), ["Software Developer", "Systems Analyst", "Database Administrator", "IT Support Specialist"]),
    (("networking", "network"), ["Network Administrator", "Network Engineer", "Systems Administrator", "IT Support Specialist"]),
    (("health informatics", "health information", "hospital administration"), ["Health Information Manager", "Hospital Administrator", "Clinical Data Analyst", "Health Services Manager"]),
    (("nursing", "midwifery", "midwife"), ["Registered Nurse", "Community Health Nurse", "Clinical Nurse", "Nursing Specialist"]),
    (("agriculture", "agricultural", "animal science", "crop", "horticulture"), ["Agricultural Officer", "Agricultural Extension Officer", "Farm Manager", "Agribusiness Officer"]),
    (("education", "teaching", "teacher"), ["Teacher", "Curriculum Developer", "Education Officer", "Teaching and Learning Resource Developer"]),
    (("engineering", "electrical", "electronics", "mechanical", "civil"), ["Professional Engineer", "Engineering Technologist", "Project Engineer", "Technical Consultant"]),
    (("safety", "environmental"), ["Health and Safety Officer", "Environmental Officer", "Risk Manager", "Compliance Officer"]),
    (("social work", "social science"), ["Social Worker", "Community Development Officer", "Youth Programme Officer", "Social Researcher"]),
    (("law", "legal"), ["Legal Advisor", "Legal Officer", "Compliance Officer", "Human Rights Officer"]),
    (("chemistry", "physics", "biology", "science"), ["Laboratory Technologist", "Research Scientist", "Science Teacher", "Quality Control Analyst"]),
    (("accounting", "bookkeeping", "pastel", "cima", "acca", "cipfa"), ["Accounting Technician", "Bookkeeper", "Auditor", "Finance Officer"]),
]


def text(record: dict[str, Any]) -> str:
    return " ".join(str(record.get(key) or "") for key in ("name", "category", "faculty", "overview")).lower()


def infer_careers(record: dict[str, Any]) -> list[str]:
    haystack = text(record)
    for keywords, careers in SPECIFIC_CAREER_RULES:
        if any(keyword in haystack for keyword in keywords):
            return careers
    for keywords, careers in CAREER_RULES:
        if any(keyword in haystack for keyword in keywords):
            return careers
    category = str(record.get("category") or "").lower()
    if "health" in category:
        return ["Health Services Officer", "Community Health Worker", "Health Programme Coordinator", "Research Assistant"]
    if "business" in category or "commerce" in category:
        return ["Business Analyst", "Operations Officer", "Business Development Officer", "Entrepreneur"]
    if "education" in category:
        return ["Teacher", "Education Officer", "Curriculum Developer", "Training Coordinator"]
    return ["Programme Specialist", "Project Officer", "Research Assistant", "Community Development Officer"]


def is_degree(record: dict[str, Any]) -> bool:
    value = f"{record.get('level') or ''} {record.get('name') or ''}".lower()
    return any(token in value for token in ("degree", "bachelor", "bsc", "b.a", "b bus", "beng", "btech"))


def inferred_duration(record: dict[str, Any]) -> str | None:
    institution = record.get("institution")
    level = str(record.get("level") or "").lower()
    name = str(record.get("name") or "").lower()
    if institution == "Limkokwing University Lesotho":
        return "4 years with project" if is_degree(record) else "3 years with attachment"
    if institution == "Botho University Lesotho":
        return "4 years with attachment"
    if institution == "Lerotholi Polytechnic":
        return "3 years with attachment" if not any(token in level for token in ("certificate", "short")) else "2 years"
    if institution in {"National University of Lesotho", "NUL Institute of Extra Mural Studies (IEMS)"}:
        if is_degree(record):
            return "5 years with attachment and project"
        if "diploma" in level or "diploma" in name:
            return "3 years"
        if "certificate" in level or "certificate" in name:
            return "2 years"
        return "3 years"
    if institution == "Lesotho College of Education":
        if is_degree(record):
            return "4 years"
        return "2 years" if "certificate" in level else "3 years"
    if institution == "Lesotho Agricultural College":
        return "3 years"
    if institution == "Centre for Accounting Studies":
        return "3 years"
    if institution == "Roma College of Nursing":
        return "3 years" if "diploma" in level or "nursing" in name else "2 years"
    return None


def load_fee_sources() -> dict[str, tuple[str, dict[str, Any]]]:
    sources: dict[str, tuple[str, dict[str, Any]]] = {}
    for path in sorted((REAL_DIR / "fees").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        sources.setdefault(data.get("institution"), (f"data/real/fees/{path.name}", data))
    return sources


def has_source(record: dict[str, Any]) -> bool:
    return bool(record.get("source_url") or record.get("source_path") or record.get("supporting_source_path"))


def main() -> None:
    programmes = json.loads(PROGRAMMES_FILE.read_text(encoding="utf-8"))
    fee_sources = load_fee_sources()
    changed = {"careers": 0, "durations": 0, "fee_evidence": 0, "approved": 0}
    for record in programmes:
        inferred_careers = infer_careers(record)
        if record.get("career_options") != inferred_careers:
            record["career_options"] = inferred_careers
            changed["careers"] += 1
        duration = inferred_duration(record)
        if duration and record.get("duration") != duration:
            record["duration"] = duration
            changed["durations"] += 1
        fee_source = fee_sources.get(record.get("institution"))
        if fee_source and record.get("institution") != "Limkokwing University Lesotho" and not record.get("supporting_fee_source_path"):
            path, fee = fee_source
            record["supporting_fee_source_path"] = path
            title = fee.get("source_title") or "fee schedule"
            year = fee.get("academic_year") or "current evidence"
            record["fee_note"] = f"Fee schedule available: {title} ({year}). Confirm the programme group and latest amount before payment."
            changed["fee_evidence"] += 1
        existing_note = record.get("source_note") or ""
        marker = "Auto-enriched from repository evidence and institution rules."
        if marker not in existing_note:
            record["source_note"] = f"{existing_note} {marker}".strip()
        if has_source(record) and record.get("review_status") == "needs_admin_review":
            record["review_status"] = "approved"
            changed["approved"] += 1
    PROGRAMMES_FILE.write_text(json.dumps(programmes, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps(changed, indent=2))


if __name__ == "__main__":
    main()