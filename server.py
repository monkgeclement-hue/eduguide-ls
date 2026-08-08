import json
import hashlib
import mimetypes
import os
import re
import sqlite3
import secrets
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from openai import OpenAI
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
DB_PATH = ROOT / "data" / "eduguide.db"
UPLOAD_ROOT = ROOT / "data" / "uploads"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
GRADE_VALUES = {"A*", "A", "B", "C", "D", "E", "F", "G", "X", "Z"}
GEMINI_DEFAULT_MODEL = "gemini-3.6-flash"
GEMINI_MODEL_FALLBACKS = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-latest"]
DEPRECATED_GEMINI_MODELS = {
  "gemini-2.5-flash": GEMINI_DEFAULT_MODEL,
  "gemini-2.5-pro": GEMINI_DEFAULT_MODEL,
}
SUBJECT_ALIASES = [
  {"code": "MATH", "subject": "Mathematics", "aliases": ["mathematics", "maths", "math"]},
  {"code": "ENG", "subject": "English", "aliases": ["english language", "english"]},
  {"code": "SES", "subject": "Sesotho", "aliases": ["sesotho"]},
  {"code": "PSCI", "subject": "Physical Science", "aliases": ["physical science", "physical sciences", "double science", "double sciences"]},
  {"code": "CSK", "subject": "Computer Skills", "aliases": ["computer skills", "computer studies", "computer literacy", "computer applications", "ict skills", "information and communication technology"]},
  {"code": "ACC", "subject": "Accounting", "aliases": ["accounting", "accounts"]},
  {"code": "BIO", "subject": "Biology", "aliases": ["biology", "life science"]},
  {"code": "AGR", "subject": "Agriculture", "aliases": ["agriculture", "agricultural science"]},
  {"code": "FNU", "subject": "Food & Nutrition", "aliases": ["food and nutrition", "food & nutrition", "food nutrition", "nutrition", "food studies", "home economics", "consumer science"]},
  {"code": "REL", "subject": "Religious Knowledge", "aliases": ["religious knowledge", "religious education", "religion", "divinity", "bible knowledge"]},
  {"code": "HIST", "subject": "History", "aliases": ["history"]},
  {"code": "GEO", "subject": "Geography", "aliases": ["geography"]},
  {"code": "PHY", "subject": "Physics", "aliases": ["physics"]},
  {"code": "CHEM", "subject": "Chemistry", "aliases": ["chemistry"]},
  {"code": "ECON", "subject": "Economics", "aliases": ["economics", "economy"]},
  {"code": "LIT", "subject": "English Literature", "aliases": ["english literature", "literature in english", "literature"]},
]

app = FastAPI(title="EduGuide LS AI Server")
PUBLIC_DATA_FILES = {"admin-catalog.js", "catalog.js", "source-manifest.json", "supabase-config.js"}
PUBLIC_ICON_FILES = {"icon-192.svg", "icon-512.svg", "icon-192.png", "icon-512.png", "apple-touch-icon.png"}
mimetypes.add_type("application/manifest+json", ".webmanifest")
mimetypes.add_type("image/svg+xml", ".svg")


class GuidanceRequest(BaseModel):
  profile: dict[str, Any] = Field(default_factory=dict)
  readiness: dict[str, Any] = Field(default_factory=dict)
  matches: list[dict[str, Any]] = Field(default_factory=list)
  documents: list[dict[str, Any]] = Field(default_factory=list)
  conversation: list[dict[str, Any]] = Field(default_factory=list)
  question: str | None = None
  mode: str = "guidance"


class AuthLoginRequest(BaseModel):
  email: str
  password: str


class AuthRegisterRequest(BaseModel):
  name: str
  email: str
  password: str
  district: str | None = None


class AuthProfileRequest(BaseModel):
  name: str | None = None
  district: str | None = None
  stream: str | None = None
  leavingYear: str | None = None
  incomeBand: str | None = None
  needSignals: list[str] = Field(default_factory=list)
  preferenceText: str | None = None
  grades: dict[str, str] = Field(default_factory=dict)
  documents: list[dict[str, Any]] = Field(default_factory=list)
  shortlist: list[str] = Field(default_factory=list)


class UserRoleUpdate(BaseModel):
  role: str


class UserStatusUpdate(BaseModel):
  status: str




def get_gemini_model_candidates() -> list[str]:
  requested = (os.getenv("GEMINI_MODEL") or GEMINI_DEFAULT_MODEL).strip() or GEMINI_DEFAULT_MODEL
  requested = DEPRECATED_GEMINI_MODELS.get(requested, requested)
  candidates = [requested, *GEMINI_MODEL_FALLBACKS]
  seen = set()
  return [model for model in candidates if model and not (model in seen or seen.add(model))]

def get_db_connection() -> sqlite3.Connection:
  DB_PATH.parent.mkdir(parents=True, exist_ok=True)
  connection = sqlite3.connect(DB_PATH)
  connection.row_factory = sqlite3.Row
  return connection


def init_database() -> None:
  with get_db_connection() as connection:
    connection.execute(
      """
      create table if not exists app_state (
        state_key text primary key,
        payload text not null,
        updated_at text not null default current_timestamp
      )
      """
    )
    connection.execute(
      """
      create table if not exists recommendation_runs (
        id integer primary key autoincrement,
        mode text not null default 'guidance',
        question text,
        profile_name text,
        payload text not null,
        created_at text not null default current_timestamp
      )
      """
    )
    connection.execute(
      """
      create table if not exists uploaded_documents (
        id text primary key,
        user_id text not null,
        original_name text not null,
        stored_name text not null,
        content_type text,
        size_bytes integer not null,
        storage_path text not null,
        status text not null default 'Uploaded - OCR pending',
        extraction_status text not null default 'pending',
        extraction_text text,
        extracted_grades text not null default '[]',
        extraction_error text,
        extracted_at text,
        uploaded_at text not null default current_timestamp
      )
      """
    )
    connection.execute(
      """
      create table if not exists auth_sessions (
        token text primary key,
        user_id text not null,
        created_at text not null default current_timestamp,
        last_seen_at text not null default current_timestamp
      )
      """
    )
    existing_columns = {
      row["name"]
      for row in connection.execute("pragma table_info(uploaded_documents)").fetchall()
    }
    document_migrations = {
      "extraction_status": "alter table uploaded_documents add column extraction_status text not null default 'pending'",
      "extraction_text": "alter table uploaded_documents add column extraction_text text",
      "extracted_grades": "alter table uploaded_documents add column extracted_grades text not null default '[]'",
      "extraction_error": "alter table uploaded_documents add column extraction_error text",
      "extracted_at": "alter table uploaded_documents add column extracted_at text",
    }
    for column, statement in document_migrations.items():
      if column not in existing_columns:
        connection.execute(statement)
    connection.commit()


init_database()


def check_sqlite_ready() -> bool:
  try:
    with get_db_connection() as connection:
      connection.execute("select 1").fetchone()
    return True
  except Exception:
    return False


def check_upload_storage_ready() -> bool:
  try:
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    probe = UPLOAD_ROOT / f".health-{uuid.uuid4().hex}"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink(missing_ok=True)
    return True
  except Exception:
    return False


def sanitize_storage_segment(value: str, fallback: str = "item") -> str:
  cleaned = re.sub(r"[^a-zA-Z0-9_.-]", "-", value or "").strip(".-")
  return cleaned[:80] or fallback


def sanitize_upload_filename(filename: str) -> str:
  name = Path(filename or "document").name
  cleaned = re.sub(r"[^a-zA-Z0-9_. -]", "_", name).strip(" .")
  return cleaned[:120] or "document"


def document_response(row: sqlite3.Row) -> dict[str, Any]:
  try:
    extracted_grades = json.loads(row["extracted_grades"] or "[]")
  except (json.JSONDecodeError, KeyError):
    extracted_grades = []
  extraction_text = row["extraction_text"] if "extraction_text" in row.keys() else None
  return {
    "id": row["id"],
    "userId": row["user_id"],
    "name": row["original_name"],
    "storedName": row["stored_name"],
    "contentType": row["content_type"],
    "size": row["size_bytes"],
    "status": row["status"],
    "uploadedAt": row["uploaded_at"],
    "url": f"/api/documents/{row['id']}/download",
    "extractionStatus": row["extraction_status"] if "extraction_status" in row.keys() else "pending",
    "extractedGrades": extracted_grades,
    "extractedTextPreview": (extraction_text or "")[:500],
    "extractionError": row["extraction_error"] if "extraction_error" in row.keys() else None,
    "extractedAt": row["extracted_at"] if "extracted_at" in row.keys() else None,
  }


DEVELOPER_PROMPT = """
You are EduGuide LS, an academic guidance assistant for students in Lesotho.
Use only the provided matcher payload. Do not invent institutions, fees, requirements,
sponsorship decisions, or official admissions outcomes.
Respect the matcher tier: "qualified" means currently meets captured rules, "almost"
means close or missing a small requirement, and "explore" means interest fit only.
Never upgrade a programme beyond the tier supplied by the matcher. Do not recommend
science, technology, engineering, health-science, or architecture pathways unless
the matcher payload already includes them as realistic options. Missing Mathematics,
Physical Science, Biology, or another hard subject gate must be treated as a blocker,
not as something the AI can overlook because the student is interested.
Uploaded documents may include OCR/text extraction metadata. Treat extracted grades
as machine-read suggestions until the student applies or confirms them in the grade
form. Do not present extracted grades as an official transcript interpretation.

Answer the student's question when one is provided. Use the recent conversation only for context and continuity; the current matcher payload remains the source of truth. If mode is "compare", compare the strongest realistic options instead of repeating generic advice.

Return concise JSON with exactly these keys:
- summary: string
- direct_answer: string
- top_recommendations: array of objects with programme, institution, tier, why, caution, action
- comparison: array of objects with programme, institution, tier, strength, concern
- study_plan: array of short strings
- document_checklist: array of short strings
- scholarship_note: string
- next_questions: array of short strings

Be warm, direct, and practical. If data confidence is low or a requirement is marked
under review, say the student should verify it with the institution/admin.
"""


def get_secret(name: str, *placeholders: str) -> str | None:
  value = os.getenv(name, "").strip()
  if not value or value in placeholders:
    return None
  return value


def get_gemini_api_key() -> str | None:
  return get_secret("GEMINI_API_KEY", "replace_with_your_gemini_api_key")


def get_openai_api_key() -> str | None:
  return get_secret("OPENAI_API_KEY", "replace_with_your_openai_api_key")


def get_ai_provider() -> str:
  provider = os.getenv("AI_PROVIDER", "gemini").strip().lower()
  return provider if provider in {"gemini", "openai"} else "gemini"


def guess_mime_type(path: Path, fallback: str | None = None) -> str:
  return fallback or mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def normalize_ocr_text(text: str) -> str:
  return re.sub(r"[ \t]+", " ", (text or "").replace("\r", "\n")).strip()


def extract_text_locally(path: Path, content_type: str | None = None) -> str:
  suffix = path.suffix.lower()
  mime_type = guess_mime_type(path, content_type)
  if suffix == ".pdf" or mime_type == "application/pdf":
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return normalize_ocr_text("\n".join(page.extract_text() or "" for page in reader.pages))
  if suffix == ".docx" or mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
    from docx import Document

    document = Document(str(path))
    lines = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
      for row in table.rows:
        lines.append(" | ".join(cell.text for cell in row.cells))
    return normalize_ocr_text("\n".join(lines))
  if suffix in {".txt", ".csv", ".tsv"} or mime_type.startswith("text/"):
    return normalize_ocr_text(path.read_text(encoding="utf-8", errors="ignore"))
  return ""


def extract_text_with_gemini_ocr(path: Path, content_type: str | None = None) -> str:
  api_key = get_gemini_api_key()
  if not api_key:
    raise RuntimeError("Gemini API key is not configured for OCR.")

  from google import genai
  from google.genai import types

  mime_type = guess_mime_type(path, content_type)
  file_part = types.Part.from_bytes(data=path.read_bytes(), mime_type=mime_type)
  client = genai.Client(api_key=api_key)
  last_error: Exception | None = None
  for model in get_gemini_model_candidates():
    try:
      response = client.models.generate_content(
        model=model,
        contents=[
          "Extract all visible text from this results slip, transcript, or academic document. Return plain text only. Preserve subject names and grade symbols such as A*, A, B, C, D, E, F, G, X, and Z.",
          file_part,
        ],
      )
      return normalize_ocr_text(response.text or "")
    except Exception as exc:
      last_error = exc
      if "NOT_FOUND" not in str(exc) and "not found" not in str(exc).lower() and "no longer available" not in str(exc).lower():
        raise
  raise RuntimeError(f"Gemini OCR failed for available model fallbacks: {last_error}")


def should_use_vision_ocr(path: Path, content_type: str | None, local_text: str) -> bool:
  suffix = path.suffix.lower()
  mime_type = guess_mime_type(path, content_type)
  if mime_type.startswith("image/"):
    return True
  if suffix == ".pdf" or mime_type == "application/pdf":
    return len(local_text) < 80
  return False


def grade_pattern() -> re.Pattern[str]:
  return re.compile(r"(?<![A-Z0-9])(?:A\*|[A-GXZ])(?![A-Z0-9*])", re.IGNORECASE)


def grade_from_nearby_text(text: str, alias: str) -> tuple[str | None, int | None]:
  lower = text.lower()
  alias_index = lower.find(alias.lower())
  if alias_index < 0:
    return None, None

  candidates = []
  for match in grade_pattern().finditer(text.upper()):
    distance = min(abs(match.start() - alias_index), abs(match.end() - (alias_index + len(alias))))
    if distance <= 90:
      candidates.append((distance, match.group(0).upper()))
  if not candidates:
    return None, None
  candidates.sort(key=lambda item: item[0])
  return candidates[0][1], candidates[0][0]


def parse_extracted_grades(text: str) -> list[dict[str, Any]]:
  extracted: dict[str, dict[str, Any]] = {}
  lines = [line.strip(" |:-") for line in normalize_ocr_text(text).split("\n") if line.strip()]
  searchable_units = lines + [normalize_ocr_text(text)]

  for subject in SUBJECT_ALIASES:
    for alias in sorted(subject["aliases"], key=len, reverse=True):
      for unit in searchable_units:
        if alias.lower() not in unit.lower():
          continue
        grade, distance = grade_from_nearby_text(unit, alias)
        if grade not in GRADE_VALUES:
          continue
        confidence = 0.88 if unit in lines and (distance or 99) <= 35 else 0.68
        current = extracted.get(subject["code"])
        if current and current["confidence"] >= confidence:
          continue
        extracted[subject["code"]] = {
          "code": subject["code"],
          "subject": subject["subject"],
          "grade": grade,
          "confidence": confidence,
          "evidence": unit[:180],
        }
  return sorted(extracted.values(), key=lambda item: item["subject"])


def update_document_extraction(document_id: str, status: str, text: str = "", grades: list[dict[str, Any]] | None = None, error: str | None = None) -> sqlite3.Row:
  final_status = "Uploaded - OCR extracted" if grades else "Uploaded - OCR checked"
  if status == "failed":
    final_status = "Uploaded - OCR failed"
  elif status == "no_text":
    final_status = "Uploaded - no readable text detected"
  elif status == "no_grades":
    final_status = "Uploaded - no grades detected"

  with get_db_connection() as connection:
    connection.execute(
      """
      update uploaded_documents
      set status = ?,
        extraction_status = ?,
        extraction_text = ?,
        extracted_grades = ?,
        extraction_error = ?,
        extracted_at = current_timestamp
      where id = ?
      """,
      (final_status, status, text[:20000], json.dumps(grades or [], ensure_ascii=False), error, document_id),
    )
    connection.commit()
    return connection.execute("select * from uploaded_documents where id = ?", (document_id,)).fetchone()


def extract_document(document_id: str) -> sqlite3.Row:
  with get_db_connection() as connection:
    row = connection.execute("select * from uploaded_documents where id = ?", (document_id,)).fetchone()
  if not row:
    raise HTTPException(status_code=404, detail="Document not found.")

  path = ROOT / row["storage_path"]
  if not path.exists():
    return update_document_extraction(document_id, "failed", error="Stored document file is missing.")

  try:
    local_error = None
    try:
      local_text = extract_text_locally(path, row["content_type"])
    except Exception as exc:
      local_text = ""
      local_error = str(exc)
    if should_use_vision_ocr(path, row["content_type"], local_text):
      text = extract_text_with_gemini_ocr(path, row["content_type"])
    else:
      if local_error:
        raise RuntimeError(local_error)
      text = local_text
    if not text.strip():
      return update_document_extraction(document_id, "no_text")
    grades = parse_extracted_grades(text)
    return update_document_extraction(document_id, "extracted" if grades else "no_grades", text=text, grades=grades)
  except Exception as exc:
    return update_document_extraction(document_id, "failed", error=str(exc))


def compact_match(match: dict[str, Any]) -> dict[str, Any]:
  scores = match.get("scores") or match.get("match") or {}
  return {
    "programme": match.get("title"),
    "institution": match.get("institution"),
    "duration": match.get("duration"),
    "faculty": match.get("faculty"),
    "careers": (match.get("careers") or [])[:4],
    "skills": (match.get("skills") or [])[:4],
    "requirements": (match.get("requirements") or [])[:4],
    "scores": {
      "overall": scores.get("overall"),
      "academic": scores.get("academic"),
      "interest": scores.get("interest") or scores.get("interests"),
      "eligibility": scores.get("eligibility"),
      "funding": scores.get("funding"),
      "funding_breakdown": scores.get("fundingBreakdown") or scores.get("funding_breakdown"),
      "confidence": scores.get("confidence"),
    },
    "tier": scores.get("tier") or match.get("tier"),
    "tier_label": scores.get("tierLabel") or match.get("tierLabel"),
    "requirement_gaps": (scores.get("requirementGaps") or match.get("requirementGaps") or [])[:4],
    "reasons": (scores.get("reasons") or match.get("reasons") or [])[:3],
    "cautions": (scores.get("cautions") or match.get("cautions") or [])[:3],
  }


def build_fallback(payload: GuidanceRequest, error: str | None = None) -> dict[str, Any]:
  top_matches = [compact_match(item) for item in payload.matches[:3]]
  best = top_matches[0] if top_matches else {}
  programme = best.get("programme") or "your strongest current match"
  institution = best.get("institution") or "the matched institution"
  cautions = best.get("cautions") or []
  caution = cautions[0] if cautions else "Verify final requirements before applying."
  question = (payload.question or "").strip()
  uploaded_documents = [item for item in payload.documents if item.get("name")]
  extracted_grade_count = sum(len(item.get("extractedGrades") or []) for item in uploaded_documents)
  document_checklist = [
    "Certificates, results slip, or transcript",
    "National ID, passport, or birth certificate",
    "Admission, application, or registration evidence",
    "Bank account confirmation",
    "Residence/chief letter or guarantor evidence",
    "Prior NMDS, CHE evaluation, CV, or study leave if applicable",
  ]
  if uploaded_documents:
    uploaded_names = ", ".join(item["name"] for item in uploaded_documents[:3])
    more_note = " and more" if len(uploaded_documents) > 3 else ""
    document_checklist = [
      f"Uploaded: {uploaded_names}{more_note}",
      f"Machine-detected grade suggestions: {extracted_grade_count}. Confirm them in the grade form before relying on matches.",
      "Keep ID/birth certificate, bank confirmation, and admission/application evidence ready.",
      "If applicable, prepare residence/chief/guarantor evidence, prior NMDS documents, CHE evaluation, CV, or study leave letter.",
    ]

  response = {
    "summary": f"Your strongest current match is {programme} at {institution}. The matcher should still be treated as guidance, not an admission decision.",
    "direct_answer": (
      f"For your question: {question} Based on the current matches, start with {programme} at {institution}, then check the tier, requirement gaps, and cautions before applying."
      if question
      else "Use the tier labels first: qualified options are strongest, almost options need small fixes or confirmation, and explore options are interest-fit pathways."
    ),
    "top_recommendations": [
      {
        "programme": item.get("programme"),
        "institution": item.get("institution"),
        "tier": item.get("tier_label") or item.get("tier") or "Explore",
        "why": "; ".join(item.get("reasons") or ["It aligns with your selected profile signals."]),
        "caution": "; ".join(item.get("cautions") or ["Confirm requirements with the institution."]),
        "action": "Compare requirements, duration, careers, and funding readiness before shortlisting.",
      }
      for item in top_matches
    ],
    "comparison": [
      {
        "programme": item.get("programme"),
        "institution": item.get("institution"),
        "tier": item.get("tier_label") or item.get("tier") or "Explore",
        "strength": "; ".join(item.get("reasons") or ["Good profile alignment."]),
        "concern": "; ".join(item.get("requirement_gaps") or item.get("cautions") or ["Confirm final entry requirements."]),
      }
      for item in top_matches
    ],
    "study_plan": [
      "Keep Mathematics and English strong because many programmes use them for ranking.",
      "Focus revision on subjects connected to your top three matched pathways.",
      "Use the caution notes to identify missing or weak requirement areas.",
    ],
    "document_checklist": document_checklist,
    "scholarship_note": "The scholarship/NMDS-style score is only an estimate. Review academic fit, background/need, priority-programme alignment, and the sponsorship document checklist before treating a pathway as funding-ready. Final sponsorship decisions remain with the official portal and NMDS process.",
    "next_questions": [
      "Which of the top matches feels most realistic for your marks?",
      "Do you want to compare careers, fees, or requirements first?",
      "Which missing document can you upload next?",
    ],
  }
  if error:
    response["summary"] = f"{response['summary']} AI service note: {error}"
  if caution and response["top_recommendations"]:
    response["top_recommendations"][0]["caution"] = caution
  return response


def parse_json_response(text: str) -> dict[str, Any] | None:
  cleaned = text.strip()
  fenced = re.search(r"```(?:json)?\s*(.*?)```", cleaned, flags=re.DOTALL | re.IGNORECASE)
  if fenced:
    cleaned = fenced.group(1).strip()
  try:
    return json.loads(cleaned)
  except json.JSONDecodeError:
    return None


def build_request_payload(payload: GuidanceRequest) -> dict[str, Any]:
  return {
    "task": {
      "mode": payload.mode if payload.mode in {"guidance", "compare"} else "guidance",
      "question": (payload.question or "").strip(),
    },
    "profile": payload.profile,
    "readiness": payload.readiness,
    "documents": payload.documents,
    "conversation": [
      {
        "role": str(item.get("role", "user"))[:20],
        "content": str(item.get("content", ""))[:900],
      }
      for item in payload.conversation[-12:]
      if isinstance(item, dict) and str(item.get("content", "")).strip()
    ],
    "matches": [compact_match(item) for item in payload.matches[:8]],
  }


def save_recommendation_run(payload: GuidanceRequest, request_payload: dict[str, Any]) -> None:
  try:
    with get_db_connection() as connection:
      connection.execute(
        """
        insert into recommendation_runs (mode, question, profile_name, payload)
        values (?, ?, ?, ?)
        """,
        (
          request_payload.get("task", {}).get("mode", "guidance"),
          request_payload.get("task", {}).get("question") or None,
          (request_payload.get("profile") or {}).get("name"),
          json.dumps(request_payload, ensure_ascii=False),
        ),
      )
      connection.commit()
  except Exception:
    pass


def normalize_email(value: str | None) -> str:
  return (value or "").strip().lower()


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
  password_salt = salt or secrets.token_hex(16)
  digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), password_salt.encode("utf-8"), 180_000)
  return password_salt, digest.hex()


def verify_password(password: str, user: dict[str, Any]) -> bool:
  password_hash = user.get("passwordHash")
  password_salt = user.get("passwordSalt")
  if password_hash and password_salt:
    _, digest = hash_password(password, password_salt)
    return secrets.compare_digest(digest, str(password_hash))
  legacy_password = user.get("password")
  return bool(legacy_password) and secrets.compare_digest(str(legacy_password), password)


def load_state_payload(state_key: str, fallback: Any = None) -> Any:
  with get_db_connection() as connection:
    row = connection.execute("select payload from app_state where state_key = ?", (state_key,)).fetchone()
  if not row:
    return fallback
  try:
    return json.loads(row["payload"])
  except json.JSONDecodeError:
    return fallback


def save_state_payload(state_key: str, payload: Any) -> None:
  serialized = json.dumps(payload, ensure_ascii=False)
  with get_db_connection() as connection:
    connection.execute(
      """
      insert into app_state (state_key, payload, updated_at)
      values (?, ?, current_timestamp)
      on conflict(state_key) do update set
        payload = excluded.payload,
        updated_at = current_timestamp
      """,
      (state_key, serialized),
    )
    connection.commit()


def now_iso() -> str:
  return __import__("datetime").datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def add_user_activity(user: dict[str, Any], activity_type: str, label: str, actor: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> None:
  timestamp = now_iso()
  activity = user.setdefault("activity", [])
  activity.insert(
    0,
    {
      "id": f"act-{uuid.uuid4().hex[:12]}",
      "type": activity_type,
      "label": label,
      "at": timestamp,
      "actorId": (actor or user).get("id"),
      "actorName": (actor or user).get("name", "System"),
      "metadata": metadata or {},
    },
  )
  user["activity"] = activity[:45]
  user["lastActiveAt"] = timestamp
  user["lastActivity"] = label


def normalize_auth_user(user: dict[str, Any]) -> dict[str, Any] | None:
  email = normalize_email(user.get("email"))
  if not email or user.get("id") in {"demo-student", "demo-admin"}:
    return None
  created_at = user.get("createdAt") or now_iso()
  return {
    "id": user.get("id") or f"user-{uuid.uuid4().hex[:12]}",
    "name": (user.get("name") or email).strip(),
    "email": email,
    "passwordHash": user.get("passwordHash"),
    "passwordSalt": user.get("passwordSalt"),
    "password": user.get("password"),
    "role": user.get("role") if user.get("role") in {"owner", "admin", "student"} else "student",
    "status": user.get("status") or "active",
    "district": user.get("district") or "",
    "phone": user.get("phone") or "",
    "stream": user.get("stream") or "",
    "leavingYear": user.get("leavingYear") or "",
    "incomeBand": user.get("incomeBand") or "mid",
    "needSignals": user.get("needSignals") if isinstance(user.get("needSignals"), list) else [],
    "preferenceText": user.get("preferenceText") or "",
    "grades": user.get("grades") if isinstance(user.get("grades"), dict) else {},
    "documents": user.get("documents") if isinstance(user.get("documents"), list) else [],
    "shortlist": user.get("shortlist") if isinstance(user.get("shortlist"), list) else [],
    "createdAt": created_at,
    "reviewedAt": user.get("reviewedAt") or (created_at if user.get("role") in {"owner", "admin"} else None),
    "lastActiveAt": user.get("lastActiveAt") or created_at,
    "lastActivity": user.get("lastActivity") or "Account created",
    "activity": user.get("activity") if isinstance(user.get("activity"), list) else [],
  }


def get_auth_users_internal() -> list[dict[str, Any]]:
  payload = load_state_payload("auth_users", {"users": []})
  users = payload.get("users", []) if isinstance(payload, dict) else []
  normalized = []
  seen = set()
  for user in users:
    if not isinstance(user, dict):
      continue
    item = normalize_auth_user(user)
    if not item or item["email"] in seen:
      continue
    seen.add(item["email"])
    normalized.append(item)
  return normalized


def save_auth_users_internal(users: list[dict[str, Any]]) -> None:
  save_state_payload("auth_users", {"users": users})


def public_user(user: dict[str, Any]) -> dict[str, Any]:
  safe = {key: value for key, value in user.items() if key not in {"password", "passwordHash", "passwordSalt"}}
  return safe


def seed_bootstrap_admin() -> None:
  admin_email = normalize_email(os.getenv("ADMIN_EMAIL"))
  admin_password = (os.getenv("ADMIN_PASSWORD") or "").strip()
  if not admin_email or not admin_password:
    return
  users = get_auth_users_internal()
  existing = next((user for user in users if user["email"] == admin_email), None)
  salt, password_hash = hash_password(admin_password)
  timestamp = now_iso()
  admin_payload = {
    "name": (os.getenv("ADMIN_NAME") or "System Admin").strip(),
    "email": admin_email,
    "passwordSalt": salt,
    "passwordHash": password_hash,
    "role": "owner",
    "status": "active",
    "district": (os.getenv("ADMIN_DISTRICT") or "").strip(),
    "phone": (os.getenv("ADMIN_PHONE") or "").strip(),
    "reviewedAt": timestamp,
  }
  if existing:
    existing.update(admin_payload)
    existing.pop("password", None)
    add_user_activity(existing, "admin_bootstrap", "System admin synced from server environment", existing)
  else:
    admin_user = {
      "id": "admin-owner",
      **admin_payload,
      "stream": "",
      "leavingYear": "",
      "incomeBand": "mid",
      "needSignals": [],
      "preferenceText": "",
      "grades": {},
      "documents": [],
      "shortlist": [],
      "createdAt": timestamp,
      "lastActiveAt": timestamp,
      "lastActivity": "System admin created from server environment",
      "activity": [],
    }
    add_user_activity(admin_user, "admin_bootstrap", "System admin created from server environment", admin_user)
    users.insert(0, admin_user)
  for user in users:
    if user["email"] != admin_email and user.get("role") == "owner":
      user["role"] = "student"
      user["reviewedAt"] = None
      add_user_activity(
        user,
        "owner_demoted",
        "Owner access removed because system ownership is controlled by server environment",
        existing or user,
      )
  save_auth_users_internal(users)


def get_bearer_token(authorization: str | None) -> str:
  if not authorization or not authorization.lower().startswith("bearer "):
    raise HTTPException(status_code=401, detail="Authentication required.")
  token = authorization.split(" ", 1)[1].strip()
  if not token:
    raise HTTPException(status_code=401, detail="Authentication required.")
  return token


def require_current_user(authorization: str | None) -> dict[str, Any]:
  token = get_bearer_token(authorization)
  with get_db_connection() as connection:
    row = connection.execute("select user_id from auth_sessions where token = ?", (token,)).fetchone()
    if row:
      connection.execute("update auth_sessions set last_seen_at = current_timestamp where token = ?", (token,))
      connection.commit()
  if not row:
    raise HTTPException(status_code=401, detail="Session expired. Please login again.")
  user = next((item for item in get_auth_users_internal() if item["id"] == row["user_id"]), None)
  if not user or user.get("status") == "suspended":
    raise HTTPException(status_code=403, detail="Account is not active.")
  return user


def require_admin_user(authorization: str | None) -> dict[str, Any]:
  user = require_current_user(authorization)
  if user.get("role") not in {"owner", "admin"}:
    raise HTTPException(status_code=403, detail="Admin access required.")
  return user


def create_auth_session(user_id: str) -> str:
  token = secrets.token_urlsafe(32)
  with get_db_connection() as connection:
    connection.execute("insert into auth_sessions (token, user_id) values (?, ?)", (token, user_id))
    connection.commit()
  return token


def sanitize_database_state_payload(state_key: str, payload: Any) -> Any:
  if state_key != "auth_users" or not isinstance(payload, dict):
    return payload
  users = payload.get("users")
  if not isinstance(users, list):
    return payload
  cleaned_users = [public_user(user) for user in get_auth_users_internal()]
  return {**payload, "users": cleaned_users}


seed_bootstrap_admin()


@app.get("/api/db/state")
def get_database_state() -> dict[str, Any]:
  with get_db_connection() as connection:
    rows = connection.execute("select state_key, payload, updated_at from app_state").fetchall()
  state = {}
  updated_at = {}
  for row in rows:
    try:
      if row["state_key"] == "auth_users":
        continue
      state[row["state_key"]] = json.loads(row["payload"])
      updated_at[row["state_key"]] = row["updated_at"]
    except json.JSONDecodeError:
      state[row["state_key"]] = None
  return {
    "ok": True,
    "database": str(DB_PATH),
    "state": state,
    "updated_at": updated_at,
  }


@app.put("/api/db/state/{state_key}")
async def put_database_state(state_key: str, request: Request) -> dict[str, Any]:
  safe_key = re.sub(r"[^a-zA-Z0-9_-]", "", state_key).strip()
  if not safe_key:
    return {"ok": False, "error": "Invalid state key"}
  if safe_key == "auth_users":
    return {"ok": True, "state_key": safe_key, "ignored": True}
  body = await request.json()
  payload = body.get("payload", body) if isinstance(body, dict) else body
  payload = sanitize_database_state_payload(safe_key, payload)
  serialized = json.dumps(payload, ensure_ascii=False)
  with get_db_connection() as connection:
    connection.execute(
      """
      insert into app_state (state_key, payload, updated_at)
      values (?, ?, current_timestamp)
      on conflict(state_key) do update set
        payload = excluded.payload,
        updated_at = current_timestamp
      """,
      (safe_key, serialized),
    )
    connection.commit()
  return {"ok": True, "state_key": safe_key}


@app.delete("/api/db/state/{state_key}")
def delete_database_state(state_key: str) -> dict[str, Any]:
  safe_key = re.sub(r"[^a-zA-Z0-9_-]", "", state_key).strip()
  if not safe_key:
    return {"ok": False, "error": "Invalid state key"}
  with get_db_connection() as connection:
    cursor = connection.execute("delete from app_state where state_key = ?", (safe_key,))
    connection.commit()
  return {"ok": True, "state_key": safe_key, "deleted": cursor.rowcount}


@app.get("/api/auth/bootstrap")
def auth_bootstrap() -> dict[str, Any]:
  seed_bootstrap_admin()
  admin_ready = any(user.get("role") in {"owner", "admin"} for user in get_auth_users_internal())
  return {"ok": True, "adminReady": admin_ready}


@app.post("/api/auth/login")
def auth_login(payload: AuthLoginRequest) -> dict[str, Any]:
  seed_bootstrap_admin()
  email = normalize_email(payload.email)
  user = next((item for item in get_auth_users_internal() if item["email"] == email), None)
  if not user or not verify_password(payload.password, user):
    raise HTTPException(status_code=401, detail="Email or password is not correct.")
  if user.get("status") == "suspended":
    raise HTTPException(status_code=403, detail="This account is suspended.")
  users = get_auth_users_internal()
  stored = next((item for item in users if item["id"] == user["id"]), user)
  if stored.get("password"):
    salt, password_hash = hash_password(payload.password)
    stored["passwordSalt"] = salt
    stored["passwordHash"] = password_hash
    stored.pop("password", None)
  add_user_activity(stored, "login", "Logged in", stored)
  save_auth_users_internal(users)
  return {"ok": True, "token": create_auth_session(stored["id"]), "user": public_user(stored)}


@app.post("/api/auth/register")
def auth_register(payload: AuthRegisterRequest) -> dict[str, Any]:
  seed_bootstrap_admin()
  name = (payload.name or "").strip()
  email = normalize_email(payload.email)
  password = payload.password or ""
  if not name or not email or not password:
    raise HTTPException(status_code=400, detail="Name, email, and password are required.")
  users = get_auth_users_internal()
  if any(user["email"] == email for user in users):
    raise HTTPException(status_code=409, detail="That email already has an account.")
  salt, password_hash = hash_password(password)
  timestamp = now_iso()
  user = {
    "id": f"user-{uuid.uuid4().hex[:12]}",
    "name": name,
    "email": email,
    "passwordSalt": salt,
    "passwordHash": password_hash,
    "role": "student",
    "status": "active",
    "district": (payload.district or "").strip(),
    "stream": "",
    "leavingYear": "",
    "incomeBand": "mid",
    "needSignals": [],
    "preferenceText": "",
    "grades": {},
    "documents": [],
    "shortlist": [],
    "createdAt": timestamp,
    "reviewedAt": None,
    "lastActiveAt": timestamp,
    "lastActivity": "Student account created",
    "activity": [],
  }
  add_user_activity(user, "account_created", "Student account created", user)
  users.append(user)
  save_auth_users_internal(users)
  return {"ok": True, "token": create_auth_session(user["id"]), "user": public_user(user)}


@app.get("/api/auth/me")
def auth_me(authorization: str | None = Header(default=None)) -> dict[str, Any]:
  user = require_current_user(authorization)
  return {"ok": True, "user": public_user(user)}


@app.post("/api/auth/logout")
def auth_logout(authorization: str | None = Header(default=None)) -> dict[str, Any]:
  token = get_bearer_token(authorization)
  with get_db_connection() as connection:
    connection.execute("delete from auth_sessions where token = ?", (token,))
    connection.commit()
  return {"ok": True}


@app.put("/api/auth/me")
def auth_update_me(payload: AuthProfileRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
  current = require_current_user(authorization)
  users = get_auth_users_internal()
  user = next((item for item in users if item["id"] == current["id"]), None)
  if not user:
    raise HTTPException(status_code=404, detail="User not found.")
  for field in ["name", "district", "stream", "leavingYear", "incomeBand", "preferenceText"]:
    value = getattr(payload, field)
    if value is not None:
      user[field] = value
  user["needSignals"] = payload.needSignals
  user["grades"] = payload.grades
  user["documents"] = payload.documents
  user["shortlist"] = payload.shortlist
  add_user_activity(user, "profile_updated", "Updated profile", user)
  save_auth_users_internal(users)
  return {"ok": True, "user": public_user(user)}


@app.get("/api/admin/users")
def admin_list_users(authorization: str | None = Header(default=None)) -> dict[str, Any]:
  require_admin_user(authorization)
  return {"ok": True, "users": [public_user(user) for user in get_auth_users_internal()]}


@app.put("/api/admin/users/{user_id}/role")
def admin_set_user_role(user_id: str, payload: UserRoleUpdate, authorization: str | None = Header(default=None)) -> dict[str, Any]:
  actor = require_admin_user(authorization)
  if payload.role not in {"admin", "student"}:
    raise HTTPException(status_code=400, detail="Invalid role.")
  users = get_auth_users_internal()
  user = next((item for item in users if item["id"] == user_id), None)
  if not user:
    raise HTTPException(status_code=404, detail="User not found.")
  if user["id"] == actor["id"] or user.get("role") == "owner":
    raise HTTPException(status_code=400, detail="Protected account.")
  user["role"] = payload.role
  if payload.role == "admin":
    user["reviewedAt"] = user.get("reviewedAt") or now_iso()
  add_user_activity(user, "role_changed", f"Role changed to {payload.role}", actor, {"role": payload.role})
  save_auth_users_internal(users)
  return {"ok": True, "user": public_user(user), "users": [public_user(item) for item in users]}


@app.put("/api/admin/users/{user_id}/status")
def admin_set_user_status(user_id: str, payload: UserStatusUpdate, authorization: str | None = Header(default=None)) -> dict[str, Any]:
  actor = require_admin_user(authorization)
  if payload.status not in {"active", "suspended"}:
    raise HTTPException(status_code=400, detail="Invalid status.")
  users = get_auth_users_internal()
  user = next((item for item in users if item["id"] == user_id), None)
  if not user:
    raise HTTPException(status_code=404, detail="User not found.")
  if user["id"] == actor["id"] or user.get("role") == "owner":
    raise HTTPException(status_code=400, detail="Protected account.")
  user["status"] = payload.status
  if payload.status == "active":
    user["reviewedAt"] = user.get("reviewedAt") or now_iso()
  add_user_activity(user, "status_changed", f"Account {payload.status}", actor, {"status": payload.status})
  save_auth_users_internal(users)
  return {"ok": True, "user": public_user(user), "users": [public_user(item) for item in users]}


@app.put("/api/admin/users/{user_id}/review")
def admin_review_user(user_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
  actor = require_admin_user(authorization)
  users = get_auth_users_internal()
  user = next((item for item in users if item["id"] == user_id), None)
  if not user:
    raise HTTPException(status_code=404, detail="User not found.")
  user["reviewedAt"] = now_iso()
  add_user_activity(user, "reviewed", "Account reviewed by admin", actor)
  save_auth_users_internal(users)
  return {"ok": True, "user": public_user(user), "users": [public_user(item) for item in users]}


@app.post("/api/documents/upload")
async def upload_documents(user_id: str = Form(...), files: list[UploadFile] = File(...)) -> dict[str, Any]:
  safe_user_id = sanitize_storage_segment(user_id, "anonymous")
  if not files:
    raise HTTPException(status_code=400, detail="No documents were uploaded.")

  user_folder = UPLOAD_ROOT / safe_user_id
  user_folder.mkdir(parents=True, exist_ok=True)
  saved_documents = []

  for upload in files:
    original_name = sanitize_upload_filename(upload.filename or "document")
    extension = Path(original_name).suffix.lower()
    stored_name = f"{uuid.uuid4().hex}{extension}"
    destination = user_folder / stored_name
    size = 0

    try:
      with destination.open("wb") as output:
        while True:
          chunk = await upload.read(1024 * 1024)
          if not chunk:
            break
          size += len(chunk)
          if size > MAX_UPLOAD_BYTES:
            output.close()
            destination.unlink(missing_ok=True)
            raise HTTPException(status_code=413, detail=f"{original_name} is larger than 10 MB.")
          output.write(chunk)
    finally:
      await upload.close()

    document_id = uuid.uuid4().hex
    relative_path = destination.relative_to(ROOT).as_posix()
    with get_db_connection() as connection:
      connection.execute(
        """
        insert into uploaded_documents (
          id, user_id, original_name, stored_name, content_type, size_bytes, storage_path, status
        )
        values (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
          document_id,
          user_id,
          original_name,
          stored_name,
          upload.content_type,
          size,
          relative_path,
          "Uploaded - OCR pending",
        ),
      )
      connection.commit()
    row = extract_document(document_id)
    saved_documents.append(document_response(row))

  return {"ok": True, "documents": saved_documents}


@app.get("/api/documents/user/{user_id}")
def list_user_documents(user_id: str) -> dict[str, Any]:
  with get_db_connection() as connection:
    rows = connection.execute(
      """
      select *
      from uploaded_documents
      where user_id = ?
      order by uploaded_at desc
      """,
      (user_id,),
    ).fetchall()
  return {"ok": True, "documents": [document_response(row) for row in rows]}


@app.post("/api/documents/{document_id}/extract")
def rerun_document_extraction(document_id: str) -> dict[str, Any]:
  safe_document_id = sanitize_storage_segment(document_id)
  row = extract_document(safe_document_id)
  return {"ok": True, "document": document_response(row)}


@app.get("/api/documents/{document_id}/download")
def download_document(document_id: str) -> FileResponse:
  safe_document_id = sanitize_storage_segment(document_id)
  with get_db_connection() as connection:
    row = connection.execute("select * from uploaded_documents where id = ?", (safe_document_id,)).fetchone()
  if not row:
    raise HTTPException(status_code=404, detail="Document not found.")
  path = ROOT / row["storage_path"]
  if not path.exists():
    raise HTTPException(status_code=404, detail="Stored document file is missing.")
  return FileResponse(path, media_type=row["content_type"] or "application/octet-stream", filename=row["original_name"])


@app.delete("/api/documents/{document_id}")
def delete_document(document_id: str) -> dict[str, Any]:
  safe_document_id = sanitize_storage_segment(document_id)
  with get_db_connection() as connection:
    row = connection.execute("select * from uploaded_documents where id = ?", (safe_document_id,)).fetchone()
    if not row:
      return {"ok": True, "deleted": 0}
    connection.execute("delete from uploaded_documents where id = ?", (safe_document_id,))
    connection.commit()
  path = ROOT / row["storage_path"]
  if path.exists() and UPLOAD_ROOT in path.resolve().parents:
    path.unlink(missing_ok=True)
  return {"ok": True, "deleted": 1}


@app.get("/api/db/diagnostics")
def database_diagnostics() -> dict[str, Any]:
  with get_db_connection() as connection:
    state_rows = connection.execute("select state_key, payload, updated_at from app_state").fetchall()
    run_count = connection.execute("select count(*) as total from recommendation_runs").fetchone()["total"]
    document_count = connection.execute("select count(*) as total from uploaded_documents").fetchone()["total"]
    document_users = connection.execute(
      """
      select user_id, count(*) as total
      from uploaded_documents
      group by user_id
      order by total desc, user_id
      limit 10
      """
    ).fetchall()
    extraction_statuses = connection.execute(
      """
      select extraction_status, count(*) as total
      from uploaded_documents
      group by extraction_status
      order by total desc, extraction_status
      """
    ).fetchall()
    latest_runs = connection.execute(
      """
      select mode, question, profile_name, created_at
      from recommendation_runs
      order by id desc
      limit 5
      """
    ).fetchall()
  state_counts = {}
  for row in state_rows:
    try:
      payload = json.loads(row["payload"])
    except json.JSONDecodeError:
      payload = {}
    if row["state_key"] == "auth_users":
      state_counts[row["state_key"]] = len(payload.get("users", []))
    elif row["state_key"] == "review_state":
      state_counts[row["state_key"]] = {
        "programmes": len(payload.get("programmeStatuses", {})),
        "edits": len(payload.get("programmeEdits", {})),
        "gaps": len(payload.get("gapStatuses", {})),
      }
    else:
      state_counts[row["state_key"]] = 1
  return {
    "ok": True,
    "database": str(DB_PATH),
    "state_keys": [row["state_key"] for row in state_rows],
    "state_counts": state_counts,
    "document_count": document_count,
    "documents_by_user": [dict(row) for row in document_users],
    "document_extraction_statuses": [dict(row) for row in extraction_statuses],
    "recommendation_run_count": run_count,
    "latest_runs": [dict(row) for row in latest_runs],
  }


def call_gemini(payload: GuidanceRequest, request_payload: dict[str, Any]) -> dict[str, Any]:
  api_key = get_gemini_api_key()
  model = get_gemini_model_candidates()[0]
  if not api_key:
    return {
      "mode": "local_fallback",
      "provider": "gemini",
      "model": model,
      "guidance": build_fallback(payload, "GEMINI_API_KEY is not set, so local guidance was used."),
    }

  try:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    last_error: Exception | None = None
    for candidate_model in get_gemini_model_candidates():
      try:
        response = client.models.generate_content(
          model=candidate_model,
          contents=json.dumps(request_payload, ensure_ascii=False),
          config=types.GenerateContentConfig(
            system_instruction=DEVELOPER_PROMPT,
            response_mime_type="application/json",
          ),
        )
        text = response.text or ""
        guidance = parse_json_response(text) or build_fallback(payload, "The Gemini response was not valid JSON.")
        return {
          "mode": "gemini",
          "provider": "gemini",
          "model": candidate_model,
          "guidance": guidance,
        }
      except Exception as exc:
        last_error = exc
        if "NOT_FOUND" not in str(exc) and "not found" not in str(exc).lower() and "no longer available" not in str(exc).lower():
          raise
    raise RuntimeError(f"Gemini failed for available model fallbacks: {last_error}")
  except Exception as exc:
    return {
      "mode": "local_fallback",
      "provider": "gemini",
      "model": model,
      "guidance": build_fallback(payload, str(exc)),
    }


def call_openai(payload: GuidanceRequest, request_payload: dict[str, Any]) -> dict[str, Any]:
  api_key = get_openai_api_key()
  model = os.getenv("OPENAI_MODEL", "gpt-5.2").strip() or "gpt-5.2"
  if not api_key:
    return {
      "mode": "local_fallback",
      "provider": "openai",
      "model": model,
      "guidance": build_fallback(payload, "OPENAI_API_KEY is not set, so local guidance was used."),
    }

  try:
    client = OpenAI(api_key=api_key)
    response = client.responses.create(
      model=model,
      input=[
        {"role": "developer", "content": DEVELOPER_PROMPT},
        {"role": "user", "content": json.dumps(request_payload, ensure_ascii=False)},
      ],
    )
    text = response.output_text
    guidance = parse_json_response(text) or build_fallback(payload, "The OpenAI response was not valid JSON.")
    return {
      "mode": "openai",
      "provider": "openai",
      "model": model,
      "guidance": guidance,
      "response_id": response.id,
    }
  except Exception as exc:
    return {
      "mode": "local_fallback",
      "provider": "openai",
      "model": model,
      "guidance": build_fallback(payload, str(exc)),
    }


@app.get("/health")
def health() -> dict[str, Any]:
  provider = get_ai_provider()
  database_ready = check_sqlite_ready()
  storage_ready = check_upload_storage_ready()
  return {
    "ok": database_ready and storage_ready,
    "provider": provider,
    "ai_configured": bool(get_gemini_api_key() if provider == "gemini" else get_openai_api_key()),
    "gemini_configured": bool(get_gemini_api_key()),
    "openai_configured": bool(get_openai_api_key()),
    "database_ready": database_ready,
    "storage_ready": storage_ready,
    "model": get_gemini_model_candidates()[0] if provider == "gemini" else os.getenv("OPENAI_MODEL", "gpt-5.2"),
  }


@app.post("/api/ai/guidance")
def ai_guidance(payload: GuidanceRequest) -> dict[str, Any]:
  if not payload.matches:
    return {
      "mode": "local_fallback",
      "model": None,
      "guidance": build_fallback(payload, "No matches were sent to the AI endpoint."),
    }

  request_payload = build_request_payload(payload)
  save_recommendation_run(payload, request_payload)
  if get_ai_provider() == "openai":
    return call_openai(payload, request_payload)
  return call_gemini(payload, request_payload)


@app.get("/")
def index() -> FileResponse:
  return FileResponse(ROOT / "index.html")


@app.get("/index.html")
def index_html() -> FileResponse:
  return FileResponse(ROOT / "index.html")


@app.get("/styles.css")
def styles() -> FileResponse:
  return FileResponse(ROOT / "styles.css", media_type="text/css")


@app.get("/app.js")
def app_script() -> FileResponse:
  return FileResponse(ROOT / "app.js", media_type="application/javascript")


@app.get("/manifest.webmanifest")
def web_manifest() -> FileResponse:
  return FileResponse(ROOT / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js")
def service_worker() -> FileResponse:
  return FileResponse(ROOT / "sw.js", media_type="application/javascript")


@app.get("/icons/{file_name}")
def public_icon(file_name: str) -> FileResponse:
  if file_name not in PUBLIC_ICON_FILES:
    raise HTTPException(status_code=404, detail="Icon is not public.")
  path = ROOT / "icons" / file_name
  if not path.exists():
    raise HTTPException(status_code=404, detail="Icon not found.")
  return FileResponse(path, media_type=guess_mime_type(path))


@app.get("/data/{file_name}")
def public_data_file(file_name: str) -> FileResponse:
  if file_name not in PUBLIC_DATA_FILES:
    raise HTTPException(status_code=404, detail="File is not public.")
  path = ROOT / "data" / file_name
  if not path.exists():
    raise HTTPException(status_code=404, detail="File not found.")
  media_type = "application/javascript" if file_name.endswith(".js") else "application/json"
  return FileResponse(path, media_type=media_type)
