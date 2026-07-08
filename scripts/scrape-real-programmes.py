from __future__ import annotations

import io
import json
import re
import time
import urllib.request
from html import unescape
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "real"
INSTITUTION_DIR = OUT_DIR / "institutions"

USER_AGENT = "EduGuideLS/0.2 programme data review crawler"


def fetch(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/pdf,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def clean(value: str) -> str:
    value = unescape(value)
    value = re.sub(r"<script[\s\S]*?</script>", " ", value, flags=re.I)
    value = re.sub(r"<style[\s\S]*?</style>", " ", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "\n", value)
    value = value.replace("\xa0", " ")
    value = value.replace("\u2013", "-").replace("\u2014", "-")
    value = value.replace("\u2018", "'").replace("\u2019", "'")
    value = value.replace("\u201c", '"').replace("\u201d", '"')
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n\s*\n+", "\n", value)
    return value.strip()


def lines_from_html(html: str) -> list[str]:
    text = clean(html)
    return [line.strip(" -*\t") for line in text.splitlines() if line.strip(" -*\t")]


def slug(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "item"


def programme_id(institution: str, name: str) -> str:
    return f"{slug(institution)}-{slug(name)}"


def level_from_title(title: str) -> str:
    lower = title.lower()
    if "certificate" in lower:
        return "Certificate"
    if "diploma" in lower:
        return "Diploma"
    if "bachelor" in lower or lower.startswith(("ba ", "bsc ", "b bus", "beng", "b.com", "bsc")):
        return "Degree"
    if "master" in lower:
        return "Masters"
    if "phd" in lower or "doctor" in lower:
        return "Doctorate"
    return "Unspecified"


def category_from_title(title: str, fallback: str = "General") -> str:
    lower = title.lower()
    if any(word in lower for word in ["computer", "software", "data", "network", "cyber", "information technology", "mobile"]):
        return "Technology & ICT"
    if any(word in lower for word in ["account", "finance", "business", "commerce", "management", "marketing", "banking", "supply chain", "entrepreneur"]):
        return "Business & Commerce"
    if any(word in lower for word in ["engineer", "architecture", "construction", "electrical", "mechanical", "civil", "water", "irrigation"]):
        return "Engineering & Built Environment"
    if any(word in lower for word in ["nursing", "midwifery", "health", "hospital"]):
        return "Health Sciences"
    if any(word in lower for word in ["education", "teaching"]):
        return "Education"
    if any(word in lower for word in ["agric", "forestry", "crop", "animal", "soil"]):
        return "Agriculture"
    if any(word in lower for word in ["fashion", "film", "journalism", "communication", "design", "creative", "broadcast"]):
        return "Creative Arts & Communication"
    if any(word in lower for word in ["tourism", "hotel", "hospitality"]):
        return "Tourism & Hospitality"
    if any(word in lower for word in ["law", "legal"]):
        return "Law"
    if any(word in lower for word in ["social", "public administration", "demography", "statistics", "economics"]):
        return "Social Sciences"
    return fallback


def luct_title(line: str) -> bool:
    if line in {"Degree", "Diploma", "Certificate", "Short_course", "Short Course"}:
        return False
    return bool(
        re.match(r"^(BA|B Bus|Bachelor|BSc|Diploma|Certificate|Short Course)\b", line)
        and len(line) < 110
        and "Explore programs" not in line
    )


def parse_luct() -> list[dict]:
    institution = "Limkokwing University Lesotho"
    urls = [
        "https://www.portal.co.ls/apply/courses",
        "https://www.portal.co.ls/apply/courses?page=2",
    ]
    programmes: list[dict] = []

    for url in urls:
        html = fetch(url).decode("utf-8", errors="replace")
        lines = lines_from_html(html)
        indexes = [i for i, line in enumerate(lines) if luct_title(line)]
        for pos, index in enumerate(indexes):
            next_index = indexes[pos + 1] if pos + 1 < len(indexes) else len(lines)
            title = lines[index]
            category = lines[index - 2] if index >= 2 else category_from_title(title)
            programme_type = lines[index - 1] if index >= 1 and lines[index - 1].lower() in {"degree", "diploma", "certificate", "short_course"} else level_from_title(title)
            faculty = lines[index + 1] if index + 1 < len(lines) and lines[index + 1].startswith("Faculty") else ""
            block = [line for line in lines[index + 1 : next_index] if line not in {"OK"}]
            requirements = [line for line in block if "Requirement" not in line and not line.startswith("Faculty")]
            programmes.append(
                {
                    "id": programme_id(institution, title),
                    "institution": institution,
                    "name": title,
                    "category": category_from_title(title, category),
                    "faculty": faculty,
                    "level": programme_type.title().replace("_", " "),
                    "duration": None,
                    "requirements_summary": " ".join(requirements[:12]).strip() or None,
                    "source_url": url,
                    "source_type": "official_course_portal",
                    "extraction_method": "html_course_cards",
                    "review_status": "needs_admin_review",
                }
            )
    return dedupe(programmes)


def decode_js_text(value: str) -> str:
    value = value.replace(r"\"", '"').replace(r"\n", " ")
    return clean(value)


def parse_botho() -> list[dict]:
    institution = "Botho University Lesotho"
    page_url = "https://www.bothouniversity.com/lesotho/programmes"
    html = fetch(page_url).decode("utf-8", errors="replace")
    assets = re.findall(r'(?:src|href)="([^"]+)"', html)
    js_url = None
    for asset in assets:
        if asset.endswith(".js") and "/assets/" in asset:
            js_url = urllib.request.urljoin(page_url, asset)
            break
    if not js_url:
        return []

    bundle = fetch(js_url).decode("utf-8", errors="replace")
    positions = [match.start() for match in re.finditer(r'programName:"', bundle)]
    programmes = []
    for index, position in enumerate(positions):
        next_position = positions[index + 1] if index + 1 < len(positions) else min(len(bundle), position + 50000)
        chunk = bundle[position:next_position]
        title_match = re.search(r'programName:"((?:\\.|[^"\\])+)""?', chunk)
        if not title_match:
            title_match = re.search(r'programName:"((?:\\.|[^"\\])+)".*?', chunk)
        if not title_match:
            continue
        title = decode_js_text(title_match.group(1))
        code = extract_js_field(chunk, "code")
        credits = extract_js_number(chunk, "totalCredits")
        duration = extract_js_field(chunk, "duration")
        modules = extract_js_field(chunk, "totalModules")
        overview = extract_js_field(chunk, "overview")
        entry = extract_js_field(chunk, "entryCriteria")
        programmes.append(
            {
                "id": programme_id(institution, title),
                "institution": institution,
                "name": title,
                "code": decode_js_text(code) if code else None,
                "category": category_from_title(title),
                "faculty": None,
                "level": level_from_title(title),
                "duration": decode_js_text(duration) if duration else None,
                "total_credits": int(credits) if credits else None,
                "total_modules": decode_js_text(modules) if modules else None,
                "overview": decode_js_text(overview) if overview else None,
                "requirements_summary": decode_js_text(entry) if entry else None,
                "source_url": page_url,
                "source_asset_url": js_url,
                "source_type": "official_js_bundle",
                "extraction_method": "javascript_programme_objects",
                "review_status": "needs_admin_review",
            }
        )
    return dedupe(programmes)


def extract_js_field(chunk: str, key: str) -> str | None:
    match = re.search(rf'{re.escape(key)}:"((?:\\.|[^"\\])*)"', chunk)
    return match.group(1) if match else None


def extract_js_number(chunk: str, key: str) -> str | None:
    match = re.search(rf"{re.escape(key)}:(\d+)", chunk)
    return match.group(1) if match else None


def nul_title(line: str) -> bool:
    if not (8 <= len(line) <= 130):
        return False
    upper = line.upper()
    starts = (
        "BACHELOR",
        "DIPLOMA",
        "CERTIFICATE",
        "POSTGRADUATE",
        "MASTER",
        "PHD",
        "DOCTOR",
        "LL.B",
        "L.L.B",
        "BSC",
        "B.SC",
        "B.ENG",
    )
    if not upper.startswith(starts):
        return False
    bad = ["PROGRAMMES", "DEGREES:", "HOME", "STAFF", "REGULATIONS"]
    return not any(token in upper and upper.strip() == token for token in bad)


def parse_nul() -> list[dict]:
    institution = "National University of Lesotho"
    iems_institution = "NUL Institute of Extra Mural Studies (IEMS)"
    sources = [
        ("Science & Technology", "https://nul.ls/faculty-of-science-and-technology/academic-programmes/"),
        ("Humanities", "https://nul.ls/humanities/academic-programmes/"),
        ("Law", "https://nul.ls/faculty-of-law/academic-programmes/"),
        ("Social Sciences", "https://nul.ls/faculty-of-social-sciences/academic-programmes/"),
        ("Education", "https://nul.ls/faculty-of-education/academic-programmes/"),
        ("Agriculture", "https://nul.ls/faculty-of-agriculture/academic-programmes/"),
        ("IEMS", "https://nul.ls/iems-2/academic-programmes/"),
    ]
    programmes: list[dict] = []
    for faculty, url in sources:
        source_institution = iems_institution if faculty == "IEMS" else institution
        try:
            html = fetch(url).decode("utf-8", errors="replace")
        except Exception as error:
            programmes.append(source_error(source_institution, url, str(error)))
            continue
        lines = lines_from_html(html)
        indexes = [i for i, line in enumerate(lines) if nul_title(line)]
        for pos, index in enumerate(indexes):
            next_index = indexes[pos + 1] if pos + 1 < len(indexes) else min(len(lines), index + 55)
            title = lines[index].title().replace("L.L.B", "LL.B").replace("Ll.B", "LL.B")
            block = lines[index + 1 : next_index]
            duration = next((line for line in block[:8] if "Duration" in line or "YEARS" in line.upper() or "SEMESTERS" in line.upper()), None)
            requirement_lines = []
            capture = False
            for line in block:
                if "Requirements" in line:
                    capture = True
                    continue
                if capture and ("Career Opportunities" in line or nul_title(line)):
                    break
                if capture:
                    requirement_lines.append(line)
            programmes.append(
                {
                    "id": programme_id(source_institution, title),
                    "institution": source_institution,
                    "name": title,
                    "category": category_from_title(title, faculty),
                    "faculty": faculty,
                    "level": level_from_title(title),
                    "duration": duration,
                    "requirements_summary": " ".join(requirement_lines[:10]).strip() or None,
                    "source_url": url,
                    "source_type": "official_academic_programmes_page",
                    "extraction_method": "html_headings_and_context",
                    "review_status": "needs_admin_review",
                }
            )
    return dedupe(programmes)


def parse_paray_manual() -> list[dict]:
    institution = "Paray School of Nursing"
    source_url = "https://www.scribd.com/document/763854725/2024-2025-Final-Prospectus"
    source_path = "C:/Users/lepha/Downloads/data/Paray 2024-2025-final-prospectus.pdf"
    certificate_requirements = (
        "Applicant must possess LGCSE/COSC or equivalent. Foreign acquired qualifications should be evaluated by "
        "the Examinations Council of Lesotho before submission. Candidate must have passed a minimum of six subjects, "
        "including D or better in English Language, D or better in Mathematics, D or better in Physics/Chemistry/Biology, "
        "and D or better in any other three subjects. Working experience as a ward attendant is an added advantage."
    )
    records = [
        {
            "name": "Certificate in Nursing Assistant",
            "level": "Certificate",
            "duration": "15 months",
            "requirements_summary": certificate_requirements,
            "career_options": ["Nursing Assistant", "Clinic Assistant", "Community Care Assistant", "Care Home Assistant"],
            "source_note": "Extracted from pages 10-11 and 22 of the supplied Paray 2024/2025 prospectus PDF.",
        },
        {
            "name": "Diploma in Nursing",
            "level": "Diploma",
            "duration": "3 years",
            "requirements_summary": (
                "Applicant must possess LGCSE/COSC or equivalent. Foreign acquired qualifications should be evaluated by ECOL before submission. "
                "Candidate must have passed a minimum of six subjects, including D or better in Mathematics, D or better in English Language, "
                "C or better in Physics/Chemistry, C or better in Biology, and C or better in any other two subjects. "
                "OR Certificate in Nursing Assistant passed with merit/distinction and a minimum of five passed subjects at COSC/LGCSE. "
                "Working experience as a Nursing Assistant is an added advantage."
            ),
            "career_options": ["Nurse", "Clinic Nurse", "Community Health Nurse", "Nursing Specialist"],
            "source_note": "Extracted from pages 11-12 and 22-23 of the supplied Paray 2024/2025 prospectus PDF.",
        },
        {
            "name": "Diploma in Midwifery",
            "level": "Diploma",
            "duration": "1 year",
            "requirements_summary": (
                "Entry route is Diploma in Nursing and registration certificate with Lesotho Nursing Council (LNC), "
                "OR Diploma in Nursing second-year transcript pending final results. This is a post-basic pathway and "
                "should not be treated as direct high-school entry."
            ),
            "career_options": ["Midwife", "Maternal Health Nurse", "Maternity Unit Nurse", "Neonatal Care Nurse"],
            "source_note": "Extracted from pages 12-13 and 23 of the supplied Paray 2024/2025 prospectus PDF.",
        },
    ]
    return [
        {
            "id": programme_id(institution, record["name"]),
            "institution": institution,
            "name": record["name"],
            "category": "Health Sciences",
            "faculty": "Nursing",
            "level": record["level"],
            "duration": record["duration"],
            "requirements_summary": record["requirements_summary"],
            "career_options": record["career_options"],
            "source_url": source_url,
            "source_path": source_path,
            "source_type": "official_local_pdf",
            "extraction_method": "pdf_text_extract",
            "review_status": "needs_admin_review",
            "source_note": record["source_note"],
        }
        for record in records
    ]


def parse_ibc_manual() -> list[dict]:
    institution = "Imperial Business College"
    source_path = "C:/Users/lepha/Downloads/data/IBC prospectus-outlined-fonts.pdf"
    source_url = "https://www.imperialcollege.edu.np/"
    requirements = (
        "Minimum entry level for BBA and BHCM is Higher Secondary School Level (10+2) or equivalent "
        "A-Levels, CBSE or other courses recognised by the National Education Board of Nepal, with a "
        "minimum of second division (45% aggregate) or 2.0 CGPA and minimum Grade C in each subject. "
        "Students must also pass the college entrance test, group discussion, and interview."
    )
    records = [
        {
            "name": "Bachelor in Business Administration (BBA)",
            "category": "Business & Commerce",
            "faculty": "Management",
            "careers": [
                "Banking Officer",
                "Marketing Officer",
                "Human Resource Officer",
                "Entrepreneur",
                "Strategic Management Assistant",
            ],
            "source_note": "Visually extracted from the 2018/19 prospectus because the PDF uses outlined fonts that do not expose reliable text.",
        },
        {
            "name": "Bachelor in Health Care Management (BHCM)",
            "category": "Health Sciences",
            "faculty": "Health Care Management",
            "careers": [
                "Hospital Management Officer",
                "Health Insurance Officer",
                "Pharmaceutical Company Officer",
                "Medical Representative",
                "Health Care Facility Administrator",
            ],
            "source_note": "Visually extracted from the 2018/19 prospectus because the PDF uses outlined fonts that do not expose reliable text.",
        },
    ]
    return [
        {
            "id": programme_id(institution, record["name"]),
            "institution": institution,
            "name": record["name"],
            "category": record["category"],
            "faculty": record["faculty"],
            "level": "Degree",
            "duration": "4 years / 8 semesters",
            "requirements_summary": requirements,
            "career_options": record["careers"],
            "source_url": source_url,
            "source_path": source_path,
            "source_type": "international_prospectus_local_pdf",
            "extraction_method": "visual_pdf_review_outlined_fonts",
            "review_status": "needs_admin_review",
            "source_note": record["source_note"] + " Institution is in Kathmandu, Nepal and must be reviewed for EduGuide LS scope before publishing to students.",
        }
        for record in records
    ]


def parse_lerotholi() -> list[dict]:
    institution = "Lerotholi Polytechnic"
    source_url = "https://www.lp.ac.ls/wp-content/uploads/2024/02/lerotholi-prospectus-2024-2025-embed1.pdf"
    data = fetch(source_url)
    reader = PdfReader(io.BytesIO(data))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    source_note = "Official prospectus states that Lerotholi Polytechnic has 22 full-time programmes."
    programmes = [
        ("Business Management", "School of Enterprise and Management", "Diploma", "3 years"),
        ("Hospitality Management", "School of Enterprise and Management", "Diploma", "3 years"),
        ("Marketing Management", "School of Enterprise and Management", "Diploma", "3 years"),
        ("Administrative Information Management", "School of Enterprise and Management", "Diploma", "3 years"),
        ("Tourism Management", "School of Enterprise and Management", "Diploma", "3 years"),
        ("BEng Tech - Computer Engineering", "School of Engineering and Technology", "Degree", None),
        ("BEng Tech - Electronics and Telecommunications", "School of Engineering and Technology", "Degree", None),
        ("BEng Tech - Power Systems Engineering", "School of Engineering and Technology", "Degree", None),
        ("Mechanical Engineering", "School of Engineering and Technology", "Diploma", "3 years"),
        ("Bachelor of Engineering in Irrigation and Drainage", "School of the Built Environment", "Degree", None),
        ("Civil Engineering", "School of the Built Environment", "Diploma", "3 years"),
        ("Construction Management", "School of the Built Environment", "Diploma", "3 years"),
        ("Water & Environmental Engineering", "School of the Built Environment", "Diploma", "3 years"),
        ("Automotive", "Artisan Training Institute", "Certificate", None),
        ("Bricklaying and Plastering", "Artisan Training Institute", "Certificate", None),
        ("Carpentry and Joinery", "Artisan Training Institute", "Certificate", None),
        ("Electrical Installation", "Artisan Training Institute", "Certificate", None),
        ("Fitting and Machining", "Artisan Training Institute", "Certificate", None),
        ("Panel Beating and Spray Painting", "Artisan Training Institute", "Certificate", None),
        ("Plumbing and Sheet Metal Work", "Artisan Training Institute", "Certificate", None),
        ("Dressmaking", "Artisan Training Institute", "Certificate", None),
        ("Tailoring", "Artisan Training Institute", "Certificate", None),
    ]
    records = []
    for title, faculty, level, duration in programmes:
        records.append(
            {
                "id": programme_id(institution, title),
                "institution": institution,
                "name": title,
                "category": category_from_title(title, faculty),
                "faculty": faculty,
                "level": level,
                "duration": duration,
                "requirements_summary": requirement_hint_from_lerotholi(text, title),
                "source_url": source_url,
                "source_type": "official_prospectus_pdf",
                "extraction_method": "pdf_text_and_programme_list",
                "review_status": "needs_admin_review",
                "source_note": source_note,
            }
        )
    return records


def requirement_hint_from_lerotholi(text: str, title: str) -> str | None:
    if title in {"Civil Engineering", "Mechanical Engineering", "Water & Environmental Engineering"}:
        return "COSC/LGCSE with credit in Mathematics and Physical Science, and pass in English Language."
    if title == "Construction Management":
        return "COSC/LGCSE with credit in Mathematics and Physical Science, pass in English, plus additional subject/RPL pathways in the prospectus."
    if title in {"Business Management", "Marketing Management"}:
        return "Commercial diploma pathway; prospectus lists English, Mathematics, and commerce-related subject requirements."
    if title in {"Hospitality Management", "Tourism Management"}:
        return "Hospitality/tourism diploma pathway; prospectus lists English, Mathematics, and relevant commercial/geography/home economics requirements."
    if title == "Administrative Information Management":
        return "Prospectus lists English Language credit and additional subject/RPL pathways."
    return None


def parse_che_accredited() -> list[dict]:
    sources = [
        (
            "Roma College of Nursing",
            "https://www.che.ac.ls/roma-college-of-nursing-rcn-accredited-programmes/",
            ["Diploma in Nursing", "Diploma in Midwifery"],
        ),
        (
            "Lesotho Agricultural College",
            "https://www.che.ac.ls/lesotho-agricultural-college-lac-accredited-programmes/",
            ["Diploma in Agriculture"],
        ),
        (
            "Lesotho Agricultural College",
            "https://www.che.ac.ls/lesotho-agricultural-college-profile/",
            [
                "Diploma in Forestry and Resource Management",
                "Diploma in Home Economics",
                "Diploma in Home Economics Education",
                "Diploma in Agricultural Engineering, Land and Water Management",
            ],
        ),
    ]
    programmes = []
    for institution, url, titles in sources:
        try:
            fetch(url)
        except Exception as error:
            programmes.append(source_error(institution, url, str(error)))
            continue
        for title in titles:
            programmes.append(
                {
                    "id": programme_id(institution, title),
                    "institution": institution,
                    "name": title,
                    "category": category_from_title(title),
                    "faculty": None,
                    "level": level_from_title(title),
                    "duration": None,
                    "requirements_summary": None,
                    "source_url": url,
                    "source_type": "che_accredited_programmes_page",
                    "extraction_method": "che_accreditation_listing",
                    "review_status": "needs_admin_review",
                }
            )
    return dedupe(programmes)


def parse_cas() -> list[dict]:
    institution = "Centre for Accounting Studies"
    handbook_overrides = {
        "Certified Accounting Technician Certificate (CAT)": {
            "duration": "ACCA pathway minimum 3 academic years when continued through Strategic Professional",
            "handbook_levels": ["CAT (entry)"],
            "requirements_summary": "LGCSE/COSC with minimum 6 subjects, 4 credits including Mathematics or English or Accounting, and aggregate not exceeding 36; or Diploma/IB/Certificate from a MOET-registered TVET institution; or comparable qualifications assessed by ECOL/MOET.",
        },
        "Association of Chartered Certified Accountants (ACCA)": {
            "duration": "Minimum 3 academic years",
            "handbook_levels": ["CAT (entry)", "Applied Knowledge", "Applied Skills 1", "Applied Skills 2", "Strategic Professional"],
            "requirements_summary": "CAT entry requires LGCSE/COSC with minimum 6 subjects, 4 credits including Mathematics or English or Accounting, and aggregate not exceeding 36. Applied Knowledge entry is available to non-accounting degree holders, diploma holders from HEI/TVET, or A-Level applicants with Mathematics and English plus 3 years accounting work experience.",
        },
        "Chartered Institute of Management Accountants (CIMA)": {
            "duration": "Minimum 3.5 years",
            "handbook_levels": ["Certificate in Business Accounting", "Diploma (Operational)", "Advanced Diploma (Management)", "Chartered Management Accounting"],
            "requirements_summary": "Certificate in Business Accounting entry uses the same LGCSE/COSC requirements as CAT; or a TVET Diploma; or comparable qualifications.",
        },
        "Chartered Institute of Public Finance and Accountancy (CIPFA)": {
            "duration": "Minimum 4 years",
            "handbook_levels": ["Certificate in Municipal Finance and Accounting", "Diploma Financial Management and Audit", "Diploma Governance Risk and Taxation", "Diploma Public Financial Management"],
            "requirements_summary": "Applicant must be employed by the Government of Lesotho for at least 2 years in accounts or finance.",
        },
    }
    courses = [
        (
            "Certified Accounting Technician Certificate (CAT)",
            "https://cas.ac.ls/course/certified-accounting-certificate-cat/",
            "Certificate",
        ),
        (
            "Association of Chartered Certified Accountants (ACCA)",
            "https://cas.ac.ls/course/acca/",
            "Professional Qualification",
        ),
        (
            "Chartered Institute of Management Accountants (CIMA)",
            "https://cas.ac.ls/course/cima/",
            "Professional Qualification",
        ),
        (
            "Chartered Institute of Public Finance and Accountancy (CIPFA)",
            "https://cas.ac.ls/course/certificate-in-international-public-financial-management/",
            "Certificate",
        ),
        (
            "Bachelor of Arts in Financial Services (BAFS)",
            "https://cas.ac.ls/bachelor-of-arts-in-financial-services-bafs/",
            "Degree",
        ),
        (
            "Lesotho Professional Accountancy Programme (LePAP)",
            "https://cas.ac.ls/course/lesotho-professional-accountancy-programmelepap",
            "Professional Qualification",
        ),
        (
            "Skills Based Computer Modules",
            "https://cas.ac.ls/course/skills-based-computer-modules/",
            "Short Course",
        ),
        (
            "Corporate Training (CT)",
            "https://cas.ac.ls/course/corporate-training-ct/",
            "Short Course",
        ),
    ]
    programmes = []
    for title, url, level in courses:
        try:
            html = fetch(url).decode("utf-8", errors="replace")
            lines = lines_from_html(html)
            text = " ".join(lines)
            requirements = extract_section_text(lines, ["ENTRY REQUIREMENTS", "ADMISSION REQUIREMENTS", "OUR ENTRY REQUIREMENTS"], ["Course Syllabus", "QUALIFICATION STRUCTURE", "CAREER OPPORTUNITIES"])
            overview = first_meaningful_paragraph(lines, title)
            duration = extract_duration(text)
        except Exception as error:
            programmes.append(
                {
                    "id": programme_id(institution, title),
                    "institution": institution,
                    "name": title,
                    "category": category_from_title(title, "Business & Commerce"),
                    "faculty": "Accounting and Financial Services",
                    "level": level,
                    "duration": handbook_overrides.get(title, {}).get("duration"),
                    "overview": None,
                    "requirements_summary": handbook_overrides.get(title, {}).get("requirements_summary"),
                    "handbook_levels": handbook_overrides.get(title, {}).get("handbook_levels"),
                    "source_url": url,
                    "source_type": "official_course_page",
                    "supporting_source_path": "C:/Users/lepha/Downloads/CAS Lesotho Student-Handbook-Volume-4.pdf" if title in handbook_overrides else None,
                    "extraction_method": "known_course_listing_fetch_error",
                    "review_status": "needs_admin_review",
                    "source_note": f"Course is part of the known CAS catalogue, but the page fetch failed during this run: {error}",
                }
            )
            continue
        programmes.append(
            {
                "id": programme_id(institution, title),
                "institution": institution,
                "name": title,
                "category": category_from_title(title, "Business & Commerce"),
                "faculty": "Accounting and Financial Services",
                "level": level,
                "duration": handbook_overrides.get(title, {}).get("duration", duration),
                "overview": overview,
                "requirements_summary": handbook_overrides.get(title, {}).get("requirements_summary", requirements),
                "handbook_levels": handbook_overrides.get(title, {}).get("handbook_levels"),
                "source_url": url,
                "source_type": "official_course_page",
                "supporting_source_path": "C:/Users/lepha/Downloads/CAS Lesotho Student-Handbook-Volume-4.pdf" if title in handbook_overrides else None,
                "extraction_method": "html_course_page_plus_manual_handbook_extract" if title in handbook_overrides else "html_course_page",
                "review_status": "needs_admin_review",
            }
        )
    return dedupe(programmes)


def parse_lce() -> list[dict]:
    institution = "Lesotho College of Education"
    source_url = "https://mabumbe.com/official-lesotho-college-education-lce-courses/"
    records = [
        ("Advanced Diploma in Special Education", "ADSE", "Advanced Diploma"),
        ("Diploma in Education (Primary)", "Dip.Ed.Pri.", "Diploma"),
        ("Diploma in Education (Secondary)", "Dip.Ed.Sec", "Diploma"),
        ("Certificate in Early Childhood Education", "CECE", "Certificate"),
    ]
    programmes = []
    for title, code, level in records:
        programmes.append(
            {
                "id": programme_id(institution, title),
                "institution": institution,
                "name": title,
                "code": code,
                "category": "Education",
                "faculty": "Teacher Education",
                "level": level,
                "duration": None,
                "requirements_summary": None,
                "source_url": source_url,
                "source_type": "third_party_courses_fees_page",
                "extraction_method": "reviewed_web_page_listing",
                "review_status": "needs_admin_review",
                "source_note": "Direct script fetch is blocked by Cloudflare; programme names are from the reachable Mabumbe page and must be confirmed against LCE official materials.",
            }
        )
    official_bed_records = [
        {
            "name": "Bachelor of Education in Primary Education",
            "career_options": [
                "Primary school teacher from Grade R to Grade 7",
                "Curriculum developer",
                "Teaching and learning resource developer",
                "Textbook author",
            ],
        },
        {
            "name": "Bachelor of Education in Preschool and Foundation Phase Education",
            "career_options": [
                "Preschool to Grade 3 teacher",
                "Curriculum developer",
                "Teaching and learning resource developer",
                "Textbook author",
            ],
        },
    ]
    official_requirements = (
        "LGCSE/COSC with at least 4 subjects at C or better and 2 subjects at D or better; "
        "or AS with at least 2 subjects at C and 2 subjects at E; or a Diploma with Education "
        "(second class pass, or pass plus 2 years experience); or a Diploma without Education with pass. "
        "Certificate in Early Childhood Education is also an entry route for the Preschool and Foundation Phase programme."
    )
    for record in official_bed_records:
        programmes.append(
            {
                "id": programme_id(institution, record["name"]),
                "institution": institution,
                "name": record["name"],
                "code": None,
                "category": "Education",
                "faculty": "Teacher Education",
                "level": "Degree",
                "duration": "4 years full-time for LGCSE/COSC entrants; possible exemption route for qualifying prior qualifications",
                "mode": "Blended face-to-face and virtual classrooms",
                "requirements_summary": official_requirements,
                "career_options": record["career_options"],
                "source_url": None,
                "source_path": "C:/Users/lepha/Downloads/Lesotho College Of Education.pdf",
                "supporting_fee_source_path": "C:/Users/lepha/Downloads/Lesotho College Of Education fees.pdf",
                "source_type": "official_local_pdf",
                "extraction_method": "manual_pdf_extract",
                "review_status": "needs_admin_review",
                "source_note": "Added from the official LCE B.Ed programme document supplied locally; kept alongside older diploma/certificate records for transition-period coverage.",
            }
        )
    return programmes


def extract_section_text(lines: list[str], starts: list[str], stops: list[str], limit: int = 18) -> str | None:
    capture = False
    collected = []
    for line in lines:
        upper = line.upper()
        if not capture and any(start in upper for start in starts):
            capture = True
            continue
        if capture and any(stop.upper() in upper for stop in stops):
            break
        if capture and line not in {"Homepage"}:
            collected.append(line)
        if len(collected) >= limit:
            break
    return " ".join(collected).strip() or None


def first_meaningful_paragraph(lines: list[str], title: str) -> str | None:
    ignored = {
        "Homepage",
        "Courses",
        "what we offer",
        "Course List",
        "Apply Online",
        "READ MORE",
    }
    title_seen = False
    for line in lines:
        if title.lower() in line.lower():
            title_seen = True
            continue
        if title_seen and len(line) > 90 and line not in ignored:
            return line
    return None


def extract_duration(text: str) -> str | None:
    match = re.search(r"\b(?:offered on a|offered on|is offered on a|qualification is offered on a)?\s*(\d+\s*(?:months?|years?))\b", text, re.I)
    return match.group(1) if match else None


def source_coverage() -> list[dict]:
    return [
        {
            "name": "LUCT Tuition and Fees",
            "url": "https://www.portal.co.ls/student-portal/finance/tuition",
            "institution": "Limkokwing University Lesotho",
            "coverage_type": "finance_source",
            "status": "sign_in_or_app_data_required",
            "note": "Page loads but finance data appears locked behind the campus portal UI.",
        },
        {
            "name": "National Teachers Training College",
            "url": "https://www.africanadvice.com/1374130/Colleges/Lesotho/National_Teachers_Training_College/",
            "institution": "National Teachers Training College",
            "coverage_type": "institution_profile",
            "status": "profile_only",
            "note": "AfricanAdvice page contains contact/address details, not programme listings.",
        },
        {
            "name": "Paray School of Nursing prospectus",
            "url": "https://www.scribd.com/document/763854725/2024-2025-Final-Prospectus",
            "local_path": "C:/Users/lepha/Downloads/data/Paray 2024-2025-final-prospectus.pdf",
            "institution": "Paray School of Nursing",
            "coverage_type": "prospectus_document",
            "status": "manual_extract_added",
            "note": "Static Scribd text was not enough; the supplied local PDF is text-readable and now supports programme durations, entry requirements, modules, fees, and contact details.",
        },
        {
            "name": "Imperial Business College prospectus",
            "url": "https://www.imperialcollege.edu.np/",
            "local_path": "C:/Users/lepha/Downloads/data/IBC prospectus-outlined-fonts.pdf",
            "institution": "Imperial Business College",
            "coverage_type": "international_prospectus_document",
            "status": "visual_extract_added",
            "note": "PDF text extraction only exposes headers because content uses outlined fonts; BBA/BHCM programme facts were visually reviewed and need admin scope confirmation because the college is in Nepal.",
        },
        {
            "name": "Botho University Lesotho prospectus on Scribd",
            "url": "https://www.scribd.com/document/846880410/Botho-University-Lesotho-Prospectus-2025-1",
            "institution": "Botho University Lesotho",
            "coverage_type": "prospectus_document",
            "status": "scribd_viewer_manual_review",
            "note": "Official Botho programme page was used instead; Scribd prospectus remains a cross-check source.",
        },
        {
            "name": "Machabeng College",
            "url": "https://machcoll.co.ls/",
            "institution": "Machabeng College",
            "coverage_type": "institution_website",
            "status": "not_higher_education_programme_source",
            "note": "Website appears to be school/admissions focused rather than a higher-education programme catalogue.",
        },
        {
            "name": "Machabeng fee structure on Scribd",
            "url": "https://www.scribd.com/document/997795506/Fee-Structure-2024-2024",
            "institution": "Machabeng College",
            "coverage_type": "fee_document",
            "status": "scribd_viewer_manual_review",
            "note": "Fee document is useful for finance reference if Machabeng stays in scope.",
        },
        {
            "name": "Lesotho Agricultural College school listing",
            "url": "https://www.schoolandcollegelistings.com/LS/Maseru/105145030832776/Lesotho-Agricultural-College",
            "institution": "Lesotho Agricultural College",
            "coverage_type": "institution_profile",
            "status": "secondary_reference",
            "note": "Useful for profile/news context; CHE pages were used for accredited programme records.",
        },
        {
            "name": "School and College Listings Lesotho",
            "url": "https://www.schoolandcollegelistings.com/LS",
            "institution": None,
            "coverage_type": "directory",
            "status": "discovery_source",
            "note": "Directory can help discover institutions but should not be treated as canonical programme data.",
        },
        {
            "name": "Scribd home",
            "url": "https://www.scribd.com/home",
            "institution": None,
            "coverage_type": "document_search",
            "status": "manual_discovery_source",
            "note": "General Scribd search page; individual documents should be reviewed separately.",
        },
    ]


def source_error(institution: str, url: str, message: str) -> dict:
    return {
        "id": programme_id(institution, f"source-error-{slug(url)}"),
        "institution": institution,
        "name": "SOURCE EXTRACTION ERROR",
        "category": "Source issue",
        "faculty": None,
        "level": None,
        "duration": None,
        "requirements_summary": message,
        "source_url": url,
        "source_type": "source_error",
        "extraction_method": "error",
        "review_status": "source_error",
    }


def dedupe(programmes: list[dict]) -> list[dict]:
    seen = set()
    output = []
    for programme in programmes:
        key = (programme.get("institution"), programme.get("name", "").lower())
        if key in seen:
            continue
        seen.add(key)
        output.append(programme)
    return output


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True), encoding="utf-8")


def group_by_institution(programmes: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for programme in programmes:
        grouped.setdefault(programme["institution"], []).append(programme)
    return dict(sorted(grouped.items()))


def main() -> None:
    started = time.time()
    all_programmes: list[dict] = []
    extractors = [parse_luct, parse_botho, parse_nul, parse_lerotholi, parse_che_accredited, parse_cas, parse_lce, parse_paray_manual, parse_ibc_manual]
    for extractor in extractors:
        all_programmes.extend(extractor())

    all_programmes = dedupe(all_programmes)
    grouped = group_by_institution(all_programmes)

    write_json(OUT_DIR / "programmes.flat.json", all_programmes)
    write_json(OUT_DIR / "programmes.by-institution.json", grouped)
    write_json(OUT_DIR / "source-coverage.json", source_coverage())
    for institution, records in grouped.items():
        write_json(INSTITUTION_DIR / f"{slug(institution)}.json", records)

    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "programme_count": len(all_programmes),
        "institution_count": len(grouped),
        "institutions": {institution: len(records) for institution, records in grouped.items()},
        "review_status_counts": status_counts(all_programmes),
        "elapsed_seconds": round(time.time() - started, 2),
    }
    write_json(OUT_DIR / "summary.json", summary)
    print(json.dumps(summary, indent=2))


def status_counts(programmes: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for programme in programmes:
        status = programme.get("review_status", "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


if __name__ == "__main__":
    main()
