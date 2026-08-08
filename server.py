import json
import hashlib
import smtplib
import mimetypes
import os
import re
import sqlite3
import secrets
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import quote

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, Response
from openai import OpenAI
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
DB_PATH = ROOT / "data" / "eduguide.db"
UPLOAD_ROOT = ROOT / "data" / "uploads"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
DEFAULT_SUPABASE_STORAGE_BUCKET = "eduguide-documents"
AI_CHAT_HISTORY_LIMIT = 24
AI_CHAT_CONTEXT_LIMIT = 12
EMAIL_VERIFICATION_TTL_MINUTES = 10
EMAIL_VERIFICATION_RESEND_SECONDS = 45
EMAIL_VERIFICATION_MAX_ATTEMPTS = 6
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
app.add_middleware(GZipMiddleware, minimum_size=1024)
PUBLIC_DATA_FILES = {"admin-catalog.js", "catalog.js", "source-manifest.json", "supabase-config.js"}
PUBLIC_ICON_FILES = {"icon-192.svg", "icon-512.svg", "icon-192.png", "icon-512.png", "apple-touch-icon.png"}
mimetypes.add_type("application/manifest+json", ".webmanifest")
mimetypes.add_type("image/svg+xml", ".svg")
NO_CACHE_HEADERS = {"Cache-Control": "no-cache, max-age=0, must-revalidate", "X-Content-Type-Options": "nosniff"}
STATIC_CACHE_HEADERS = {"Cache-Control": "public, max-age=300, stale-while-revalidate=86400", "X-Content-Type-Options": "nosniff"}
IMMUTABLE_CACHE_HEADERS = {"Cache-Control": "public, max-age=604800, immutable", "X-Content-Type-Options": "nosniff"}


class GuidanceRequest(BaseModel):
  profile: dict[str, Any] = Field(default_factory=dict)
  readiness: dict[str, Any] = Field(default_factory=dict)
  matches: list[dict[str, Any]] = Field(default_factory=list)
  blockedMatches: list[dict[str, Any]] = Field(default_factory=list)
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
  code: str | None = None


class AuthVerifyRegistrationRequest(AuthRegisterRequest):
  code: str


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
      create table if not exists ai_chat_messages (
        id text primary key,
        user_id text not null,
        role text not null,
        content text not null,
        payload text,
        created_at text not null default current_timestamp
      )
      """
    )
    connection.execute(
      """
      create index if not exists idx_ai_chat_messages_user_created
      on ai_chat_messages(user_id, created_at desc)
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
    connection.execute(
      """
      create table if not exists email_verifications (
        id text primary key,
        email text not null,
        purpose text not null default 'registration',
        code_hash text not null,
        code_salt text not null,
        payload text not null default '{}',
        attempts integer not null default 0,
        created_at text not null,
        expires_at text not null,
        consumed_at text
      )
      """
    )
    connection.execute(
      """
      create index if not exists idx_email_verifications_email_purpose_created
      on email_verifications(email, purpose, created_at desc)
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


def check_data_backend_ready() -> bool:
  if using_supabase():
    try:
      supabase_request(
        "GET",
        supabase_table_path("runtime_app_state", "select=state_key&limit=1"),
      )
      return True
    except Exception:
      return False
  return check_sqlite_ready()


def check_document_storage_ready() -> bool:
  if using_supabase():
    try:
      supabase_request(
        "GET",
        f"/storage/v1/bucket/{quote(get_supabase_storage_bucket(), safe='')}",
        content_type=None,
      )
      return True
    except Exception:
      return False
  return check_upload_storage_ready()


def sanitize_storage_segment(value: str, fallback: str = "item") -> str:
  cleaned = re.sub(r"[^a-zA-Z0-9_.-]", "-", value or "").strip(".-")
  return cleaned[:80] or fallback


def sanitize_upload_filename(filename: str) -> str:
  name = Path(filename or "document").name
  cleaned = re.sub(r"[^a-zA-Z0-9_. -]", "_", name).strip(" .")
  return cleaned[:120] or "document"


def row_get(row: sqlite3.Row | dict[str, Any], key: str, default: Any = None) -> Any:
  if isinstance(row, sqlite3.Row):
    return row[key] if key in row.keys() else default
  if isinstance(row, dict):
    return row.get(key, default)
  return default


def parse_jsonish(value: Any, fallback: Any = None) -> Any:
  if value is None:
    return fallback
  if isinstance(value, (dict, list)):
    return value
  if isinstance(value, str):
    try:
      return json.loads(value)
    except json.JSONDecodeError:
      return fallback
  return fallback


def document_response(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
  extracted_grades = parse_jsonish(row_get(row, "extracted_grades"), [])
  extraction_text = row_get(row, "extraction_text")
  document_id = row_get(row, "id")
  try:
    if not isinstance(extracted_grades, list):
      extracted_grades = []
  except TypeError:
    extracted_grades = []
  return {
    "id": document_id,
    "userId": row_get(row, "user_id"),
    "name": row_get(row, "original_name"),
    "storedName": row_get(row, "stored_name"),
    "contentType": row_get(row, "content_type"),
    "size": row_get(row, "size_bytes"),
    "status": row_get(row, "status"),
    "uploadedAt": row_get(row, "uploaded_at"),
    "url": f"/api/documents/{document_id}/download",
    "extractionStatus": row_get(row, "extraction_status", "pending"),
    "extractedGrades": extracted_grades,
    "extractedTextPreview": (extraction_text or "")[:500],
    "extractionError": row_get(row, "extraction_error"),
    "extractedAt": row_get(row, "extracted_at"),
  }


DEVELOPER_PROMPT = """
You are EduGuide LS, an academic guidance assistant for students in Lesotho.
Use only the provided matcher payload. Do not invent institutions, fees, requirements,
sponsorship decisions, or official admissions outcomes.
Respect the matcher tier: "qualified" means currently meets captured rules, "almost"
means close or missing a small requirement, and "explore" means interest fit only.
Never upgrade a programme beyond the tier supplied by the matcher. Only put
qualified or almost programmes in top_recommendations and alternative routes;
use explore programmes for context only. Do not recommend science, technology,
engineering, health-science, or architecture pathways unless
the matcher payload already includes them as realistic options. Missing Mathematics,
Physical Science, Biology, or another hard subject gate must be treated as a blocker,
not as something the AI can overlook because the student is interested.
Respect supplied fundingBreakdown.policy values. For National University of Lesotho
and IEMS records, treat diploma/certificate or other non-degree programmes as not
NMDS sponsorship-ready when the payload says "degree+ only"; do not describe those
non-degree NUL pathways as funded options. Degree-and-higher NUL pathways may be
discussed as possible funding routes, but keep the estimate cautious and competitive.
Uploaded documents may include OCR/text extraction metadata. Treat extracted grades
as machine-read suggestions until the student applies or confirms them in the grade
form. Do not present extracted grades as an official transcript interpretation.
When application/source links and application document checklists are supplied in
the payload, use them for practical next steps. Do not invent deadlines; say
deadline tracking is not active yet unless the payload provides a verified date.

Answer the student's question when one is provided. Use the recent conversation
only for context and continuity; the current matcher payload remains the source
of truth. If mode is "compare", compare the strongest realistic qualified/almost
options instead of repeating generic advice. If mode is "interview", explain the
profile built from the interview answers, state what is still missing, and guide
the student toward the strongest qualified/almost matches produced by the matcher.
If the student asks why they are
blocked, explain the exact blocker from blocked_matches or requirement_gaps and
give a realistic next step. Ask one or two follow-up questions whenever important
profile details are missing.

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


def get_bool_env(name: str, default: bool = False) -> bool:
  value = os.getenv(name)
  if value is None:
    return default
  return value.strip().lower() in {"1", "true", "yes", "on"}


def smtp_configured() -> bool:
  return bool(get_secret("SMTP_HOST") and get_secret("SMTP_FROM_EMAIL"))


def email_debug_codes_enabled() -> bool:
  return get_bool_env("EMAIL_DEBUG_CODES", False)


def send_verification_email(email: str, name: str, code: str) -> None:
  smtp_host = get_secret("SMTP_HOST")
  from_email = get_secret("SMTP_FROM_EMAIL")
  if not smtp_host or not from_email:
    raise RuntimeError("SMTP_HOST and SMTP_FROM_EMAIL are required for email verification.")

  smtp_port = int(os.getenv("SMTP_PORT", "465" if get_bool_env("SMTP_USE_SSL", False) else "587"))
  from_name = os.getenv("SMTP_FROM_NAME", "EduGuide LS").strip() or "EduGuide LS"
  use_ssl = get_bool_env("SMTP_USE_SSL", False)
  use_tls = get_bool_env("SMTP_USE_TLS", not use_ssl)
  username = get_secret("SMTP_USERNAME")
  password = get_secret("SMTP_PASSWORD")

  message = EmailMessage()
  message["Subject"] = "Your EduGuide LS verification code"
  message["From"] = f"{from_name} <{from_email}>"
  message["To"] = email
  message.set_content(
    "\n".join(
      [
        f"Hello {name or 'student'},",
        "",
        f"Your EduGuide LS verification code is: {code}",
        f"It expires in {EMAIL_VERIFICATION_TTL_MINUTES} minutes.",
        "",
        "If you did not request this account, you can ignore this email.",
        "",
        "EduGuide LS",
      ]
    )
  )

  if use_ssl:
    with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=20) as server:
      if username and password:
        server.login(username, password)
      server.send_message(message)
    return

  with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
    if use_tls:
      server.starttls()
    if username and password:
      server.login(username, password)
    server.send_message(message)


def get_supabase_url() -> str | None:
  value = get_secret("SUPABASE_URL", "replace_with_your_supabase_url")
  return value.rstrip("/") if value else None


def get_supabase_service_key() -> str | None:
  return get_secret(
    "SUPABASE_SERVICE_ROLE_KEY",
    "replace_with_your_supabase_service_role_key",
  ) or get_secret("SUPABASE_SERVICE_KEY", "replace_with_your_supabase_service_role_key")


def supabase_configured() -> bool:
  return bool(get_supabase_url() and get_supabase_service_key())


def get_data_backend() -> str:
  requested = os.getenv("DATA_BACKEND", "auto").strip().lower()
  if requested == "sqlite":
    return "sqlite"
  if requested == "supabase" and not supabase_configured():
    return "sqlite"
  return "supabase" if supabase_configured() else "sqlite"


def using_supabase() -> bool:
  return get_data_backend() == "supabase"


def get_supabase_storage_bucket() -> str:
  return (os.getenv("SUPABASE_STORAGE_BUCKET") or DEFAULT_SUPABASE_STORAGE_BUCKET).strip() or DEFAULT_SUPABASE_STORAGE_BUCKET


def supabase_headers(content_type: str | None = "application/json", prefer: str | None = None) -> dict[str, str]:
  key = get_supabase_service_key()
  if not key:
    raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is not configured.")
  headers = {
    "apikey": key,
    "Authorization": f"Bearer {key}",
    "Accept": "application/json",
  }
  if content_type:
    headers["Content-Type"] = content_type
  if prefer:
    headers["Prefer"] = prefer
  return headers


def supabase_request(
  method: str,
  path: str,
  body: Any = None,
  *,
  content_type: str | None = "application/json",
  prefer: str | None = None,
  extra_headers: dict[str, str] | None = None,
  raw: bool = False,
  timeout: int = 30,
) -> Any:
  base_url = get_supabase_url()
  if not base_url:
    raise RuntimeError("SUPABASE_URL is not configured.")
  data = None
  if body is not None:
    data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
  headers = supabase_headers(content_type, prefer)
  if extra_headers:
    headers.update(extra_headers)
  request = urlrequest.Request(
    f"{base_url}{path}",
    data=data,
    method=method,
    headers=headers,
  )
  try:
    with urlrequest.urlopen(request, timeout=timeout) as response:
      payload = response.read()
      if raw:
        return payload, dict(response.headers)
      if not payload:
        return None
      return json.loads(payload.decode("utf-8"))
  except urlerror.HTTPError as exc:
    details = exc.read().decode("utf-8", errors="ignore")
    raise RuntimeError(f"Supabase {method} {path} failed with {exc.code}: {details}") from exc


def supabase_table_path(table: str, query: str = "") -> str:
  suffix = f"?{query}" if query else ""
  return f"/rest/v1/{table}{suffix}"


def supabase_filter_value(value: str) -> str:
  return quote(value, safe="")


def get_ai_provider() -> str:
  provider = os.getenv("AI_PROVIDER", "gemini").strip().lower()
  return provider if provider in {"gemini", "openai"} else "gemini"


def guess_mime_type(path: Path, fallback: str | None = None) -> str:
  return fallback or mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def cached_file_response(path: Path, media_type: str | None = None, headers: dict[str, str] | None = None, filename: str | None = None) -> FileResponse:
  return FileResponse(path, media_type=media_type or guess_mime_type(path), headers=headers or STATIC_CACHE_HEADERS, filename=filename)


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


def encoded_storage_path(storage_path: str) -> str:
  return "/".join(quote(part, safe="") for part in storage_path.split("/") if part)


def upload_supabase_storage_object(storage_path: str, content: bytes, content_type: str | None) -> None:
  supabase_request(
    "POST",
    f"/storage/v1/object/{get_supabase_storage_bucket()}/{encoded_storage_path(storage_path)}",
    content,
    content_type=content_type or "application/octet-stream",
    extra_headers={"x-upsert": "true"},
    raw=True,
    timeout=60,
  )


def download_supabase_storage_object(storage_path: str) -> bytes:
  content, _headers = supabase_request(
    "GET",
    f"/storage/v1/object/{get_supabase_storage_bucket()}/{encoded_storage_path(storage_path)}",
    content_type=None,
    raw=True,
    timeout=60,
  )
  return content


def delete_supabase_storage_object(storage_path: str) -> None:
  try:
    supabase_request(
      "DELETE",
      f"/storage/v1/object/{get_supabase_storage_bucket()}/{encoded_storage_path(storage_path)}",
      content_type=None,
      raw=True,
      timeout=30,
    )
  except Exception:
    pass


def insert_document_record(record: dict[str, Any]) -> sqlite3.Row | dict[str, Any]:
  if using_supabase():
    rows = supabase_request(
      "POST",
      supabase_table_path("runtime_uploaded_documents"),
      record,
      prefer="return=representation",
    )
    return rows[0] if rows else record

  with get_db_connection() as connection:
    connection.execute(
      """
      insert into uploaded_documents (
        id, user_id, original_name, stored_name, content_type, size_bytes, storage_path, status
      )
      values (?, ?, ?, ?, ?, ?, ?, ?)
      """,
      (
        record["id"],
        record["user_id"],
        record["original_name"],
        record["stored_name"],
        record.get("content_type"),
        record["size_bytes"],
        record["storage_path"],
        record.get("status") or "Uploaded - OCR pending",
      ),
    )
    connection.commit()
    return connection.execute("select * from uploaded_documents where id = ?", (record["id"],)).fetchone()


def get_document_record(document_id: str) -> sqlite3.Row | dict[str, Any] | None:
  if using_supabase():
    rows = supabase_request(
      "GET",
      supabase_table_path(
        "runtime_uploaded_documents",
        f"id=eq.{supabase_filter_value(document_id)}&select=*&limit=1",
      ),
    )
    return rows[0] if rows else None

  with get_db_connection() as connection:
    return connection.execute("select * from uploaded_documents where id = ?", (document_id,)).fetchone()


def list_document_records(user_id: str) -> list[sqlite3.Row | dict[str, Any]]:
  if using_supabase():
    rows = supabase_request(
      "GET",
      supabase_table_path(
        "runtime_uploaded_documents",
        f"user_id=eq.{supabase_filter_value(user_id)}&select=*&order=uploaded_at.desc",
      ),
    )
    return rows or []

  with get_db_connection() as connection:
    return connection.execute(
      """
      select *
      from uploaded_documents
      where user_id = ?
      order by uploaded_at desc
      """,
      (user_id,),
    ).fetchall()


def delete_document_record(document_id: str) -> sqlite3.Row | dict[str, Any] | None:
  if using_supabase():
    rows = supabase_request(
      "DELETE",
      supabase_table_path(
        "runtime_uploaded_documents",
        f"id=eq.{supabase_filter_value(document_id)}&select=*",
      ),
      prefer="return=representation",
    )
    return rows[0] if rows else None

  with get_db_connection() as connection:
    row = connection.execute("select * from uploaded_documents where id = ?", (document_id,)).fetchone()
    if row:
      connection.execute("delete from uploaded_documents where id = ?", (document_id,))
      connection.commit()
    return row


def update_document_extraction(document_id: str, status: str, text: str = "", grades: list[dict[str, Any]] | None = None, error: str | None = None) -> sqlite3.Row | dict[str, Any]:
  final_status = "Uploaded - OCR extracted" if grades else "Uploaded - OCR checked"
  if status == "failed":
    final_status = "Uploaded - OCR failed"
  elif status == "no_text":
    final_status = "Uploaded - no readable text detected"
  elif status == "no_grades":
    final_status = "Uploaded - no grades detected"

  if using_supabase():
    rows = supabase_request(
      "PATCH",
      supabase_table_path(
        "runtime_uploaded_documents",
        f"id=eq.{supabase_filter_value(document_id)}&select=*",
      ),
      {
        "status": final_status,
        "extraction_status": status,
        "extraction_text": text[:20000],
        "extracted_grades": grades or [],
        "extraction_error": error,
        "extracted_at": now_iso(),
      },
      prefer="return=representation",
    )
    if not rows:
      raise HTTPException(status_code=404, detail="Document not found.")
    return rows[0]

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


def extract_document(document_id: str) -> sqlite3.Row | dict[str, Any]:
  row = get_document_record(document_id)
  if not row:
    raise HTTPException(status_code=404, detail="Document not found.")

  temporary_path: Path | None = None
  if using_supabase():
    try:
      suffix = Path(str(row_get(row, "original_name") or row_get(row, "stored_name") or "document")).suffix
      with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(download_supabase_storage_object(str(row_get(row, "storage_path"))))
        temporary_path = Path(temp_file.name)
      path = temporary_path
    except Exception as exc:
      return update_document_extraction(document_id, "failed", error=str(exc))
  else:
    path = ROOT / str(row_get(row, "storage_path"))

  if not path.exists():
    return update_document_extraction(document_id, "failed", error="Stored document file is missing.")

  try:
    local_error = None
    try:
      local_text = extract_text_locally(path, row_get(row, "content_type"))
    except Exception as exc:
      local_text = ""
      local_error = str(exc)
    if should_use_vision_ocr(path, row_get(row, "content_type"), local_text):
      text = extract_text_with_gemini_ocr(path, row_get(row, "content_type"))
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
  finally:
    if temporary_path:
      temporary_path.unlink(missing_ok=True)


def compact_match(match: dict[str, Any]) -> dict[str, Any]:
  scores = match.get("scores") or match.get("match") or {}
  return {
    "programme": match.get("title"),
    "institution": match.get("institution"),
    "duration": match.get("duration"),
    "faculty": match.get("faculty"),
    "level": match.get("level"),
    "source": match.get("source"),
    "source_type": match.get("sourceType") or match.get("source_type"),
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
      "priority": scores.get("priority"),
    },
    "tier": scores.get("tier") or match.get("tier"),
    "tier_label": scores.get("tierLabel") or match.get("tierLabel"),
    "requirement_gaps": (scores.get("requirementGaps") or match.get("requirementGaps") or [])[:4],
    "reasons": (scores.get("reasons") or match.get("reasons") or [])[:3],
    "cautions": (scores.get("cautions") or match.get("cautions") or [])[:3],
  }


def is_recommendable_match(match: dict[str, Any]) -> bool:
  tier = str(match.get("tier_label") or match.get("tier") or "").lower()
  return "qualified" in tier or "almost" in tier


def build_fallback(payload: GuidanceRequest, error: str | None = None) -> dict[str, Any]:
  compact_matches = [compact_match(item) for item in payload.matches[:8]]
  top_matches = [item for item in compact_matches if is_recommendable_match(item)][:3]
  explore_matches = [item for item in compact_matches if not is_recommendable_match(item)][:3]
  blocked_matches = [compact_match(item) for item in payload.blockedMatches[:5]]
  best = top_matches[0] if top_matches else (explore_matches[0] if explore_matches else {})
  programme = best.get("programme") or "your strongest current match"
  institution = best.get("institution") or "the matched institution"
  cautions = best.get("cautions") or []
  caution = cautions[0] if cautions else "Verify final requirements before applying."
  question = (payload.question or "").strip()
  blocked_summary = ""
  if blocked_matches:
    blocked = blocked_matches[0]
    gaps = blocked.get("requirement_gaps") or blocked.get("cautions") or []
    blocked_summary = f" A blocked example is {blocked.get('programme')} at {blocked.get('institution')}: {'; '.join(gaps[:2])}."
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
    "summary": (
      f"Your strongest realistic match is {programme} at {institution}. The matcher should still be treated as guidance, not an admission decision."
      if top_matches
      else f"No qualified or almost-qualified recommendation is strong enough yet.{blocked_summary} Add/confirm grades and check requirement gaps before applying."
    ),
    "direct_answer": (
      f"For your question: {question} Based on the current evidence, use qualified/almost options first. {programme} at {institution} is the best available path to inspect, and blocked paths should only be used as future goals."
      if question
      else "Use the tier labels first: qualified options are strongest, almost options need small fixes or confirmation, and explore options are interest-fit pathways, not application recommendations."
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
      "Use blocked-pathway notes to identify missing or weak requirement areas.",
    ],
    "document_checklist": document_checklist,
    "scholarship_note": "The scholarship/NMDS-style score is only an estimate. Review academic fit, background/need, priority-programme alignment, and the sponsorship document checklist before treating a pathway as funding-ready. Final sponsorship decisions remain with the official portal and NMDS process.",
    "next_questions": [
      "Which of the qualified or almost-qualified matches feels most realistic for your marks?",
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


def build_request_payload(payload: GuidanceRequest, conversation: list[dict[str, Any]] | None = None) -> dict[str, Any]:
  compact_matches = [compact_match(item) for item in payload.matches[:8]]
  recommendable_matches = [item for item in compact_matches if is_recommendable_match(item)]
  mode = payload.mode if payload.mode in {"guidance", "compare", "interview"} else "guidance"
  return {
    "task": {
      "mode": mode,
      "question": (payload.question or "").strip(),
    },
    "profile": payload.profile,
    "readiness": payload.readiness,
    "documents": payload.documents,
    "recommendable_matches": recommendable_matches[:6],
    "explore_matches": [item for item in compact_matches if not is_recommendable_match(item)][:4],
    "blocked_matches": [compact_match(item) for item in payload.blockedMatches[:6]],
    "conversation": [
      {
        "id": str(item.get("id", ""))[:80],
        "role": str(item.get("role", "user"))[:20],
        "content": str(item.get("content", ""))[:900],
      }
      for item in (conversation if conversation is not None else payload.conversation)[-AI_CHAT_CONTEXT_LIMIT:]
      if isinstance(item, dict) and str(item.get("content", "")).strip()
    ],
    "matches": compact_matches,
  }


def save_recommendation_run(payload: GuidanceRequest, request_payload: dict[str, Any]) -> None:
  try:
    if using_supabase():
      supabase_request(
        "POST",
        supabase_table_path("runtime_recommendation_runs"),
        {
          "mode": request_payload.get("task", {}).get("mode", "guidance"),
          "question": request_payload.get("task", {}).get("question") or None,
          "profile_name": (request_payload.get("profile") or {}).get("name"),
          "payload": request_payload,
        },
        prefer="return=minimal",
      )
      return

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
  if using_supabase():
    rows = supabase_request(
      "GET",
      supabase_table_path(
        "runtime_app_state",
        f"state_key=eq.{supabase_filter_value(state_key)}&select=payload&limit=1",
      ),
    )
    if not rows:
      return fallback
    return parse_jsonish(rows[0].get("payload"), fallback)

  with get_db_connection() as connection:
    row = connection.execute("select payload from app_state where state_key = ?", (state_key,)).fetchone()
  if not row:
    return fallback
  try:
    return json.loads(row["payload"])
  except json.JSONDecodeError:
    return fallback


def save_state_payload(state_key: str, payload: Any) -> None:
  if using_supabase():
    supabase_request(
      "POST",
      supabase_table_path("runtime_app_state", "on_conflict=state_key"),
      {
        "state_key": state_key,
        "payload": payload,
        "updated_at": now_iso(),
      },
      prefer="resolution=merge-duplicates,return=minimal",
    )
    return

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


def list_state_payloads() -> list[dict[str, Any]]:
  if using_supabase():
    rows = supabase_request(
      "GET",
      supabase_table_path("runtime_app_state", "select=state_key,payload,updated_at&order=state_key.asc"),
    )
    return rows or []

  with get_db_connection() as connection:
    rows = connection.execute("select state_key, payload, updated_at from app_state").fetchall()
  return [
    {
      "state_key": row["state_key"],
      "payload": parse_jsonish(row["payload"], {}),
      "updated_at": row["updated_at"],
    }
    for row in rows
  ]


def delete_state_payload(state_key: str) -> int:
  if using_supabase():
    rows = supabase_request(
      "DELETE",
      supabase_table_path("runtime_app_state", f"state_key=eq.{supabase_filter_value(state_key)}&select=state_key"),
      prefer="return=representation",
    )
    return len(rows or [])

  with get_db_connection() as connection:
    cursor = connection.execute("delete from app_state where state_key = ?", (state_key,))
    connection.commit()
  return cursor.rowcount


def normalize_ai_chat_message(item: dict[str, Any] | sqlite3.Row | None) -> dict[str, Any] | None:
  if not item:
    return None
  role = "assistant" if row_get(item, "role") == "assistant" else "user"
  content = str(row_get(item, "content") or "").strip()
  if not content:
    return None
  message_id = sanitize_storage_segment(str(row_get(item, "id") or f"ai-{uuid.uuid4().hex[:12]}"), "ai-message")
  return {
    "id": message_id,
    "role": role,
    "content": content[:2400],
    "at": row_get(item, "at") or row_get(item, "created_at") or now_iso(),
  }


def merge_ai_chat_histories(*histories: list[dict[str, Any]]) -> list[dict[str, Any]]:
  merged: list[dict[str, Any]] = []
  seen: set[str] = set()
  for history in histories:
    for raw_message in history or []:
      message = normalize_ai_chat_message(raw_message)
      if not message:
        continue
      key = message["id"] if message.get("id") else f"{message['role']}:{message['content']}"
      fallback_key = f"{message['role']}:{message['content']}"
      if key in seen or fallback_key in seen:
        continue
      seen.add(key)
      seen.add(fallback_key)
      merged.append(message)
  return merged[-AI_CHAT_HISTORY_LIMIT:]


def list_ai_chat_history(user_id: str) -> list[dict[str, Any]]:
  if using_supabase():
    rows = supabase_request(
      "GET",
      supabase_table_path(
        "runtime_ai_chat_messages",
        f"user_id=eq.{supabase_filter_value(user_id)}&select=id,role,content,created_at&order=created_at.desc&limit={AI_CHAT_HISTORY_LIMIT}",
      ),
    ) or []
    return [message for message in (normalize_ai_chat_message(row) for row in reversed(rows)) if message]

  with get_db_connection() as connection:
    rows = connection.execute(
      """
      select id, role, content, created_at
      from ai_chat_messages
      where user_id = ?
      order by created_at desc
      limit ?
      """,
      (user_id, AI_CHAT_HISTORY_LIMIT),
    ).fetchall()
  return [message for message in (normalize_ai_chat_message(row) for row in reversed(rows)) if message]


def save_ai_chat_history(user_id: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
  normalized = merge_ai_chat_histories(messages)
  if using_supabase():
    supabase_request(
      "DELETE",
      supabase_table_path("runtime_ai_chat_messages", f"user_id=eq.{supabase_filter_value(user_id)}"),
      prefer="return=minimal",
    )
    if normalized:
      supabase_request(
        "POST",
        supabase_table_path("runtime_ai_chat_messages"),
        [
          {
            "id": message["id"],
            "user_id": user_id,
            "role": message["role"],
            "content": message["content"],
            "payload": {},
            "created_at": message.get("at") or now_iso(),
          }
          for message in normalized
        ],
        prefer="return=minimal",
      )
    return normalized

  with get_db_connection() as connection:
    connection.execute("delete from ai_chat_messages where user_id = ?", (user_id,))
    connection.executemany(
      """
      insert into ai_chat_messages (id, user_id, role, content, payload, created_at)
      values (?, ?, ?, ?, ?, ?)
      """,
      [
        (
          message["id"],
          user_id,
          message["role"],
          message["content"],
          "{}",
          message.get("at") or now_iso(),
        )
        for message in normalized
      ],
    )
    connection.commit()
  return normalized


def clear_ai_chat_history(user_id: str) -> None:
  if using_supabase():
    supabase_request(
      "DELETE",
      supabase_table_path("runtime_ai_chat_messages", f"user_id=eq.{supabase_filter_value(user_id)}"),
      prefer="return=minimal",
    )
    return

  with get_db_connection() as connection:
    connection.execute("delete from ai_chat_messages where user_id = ?", (user_id,))
    connection.commit()


def safe_list_ai_chat_history(user_id: str) -> list[dict[str, Any]]:
  try:
    return list_ai_chat_history(user_id)
  except Exception:
    return []


def safe_save_ai_chat_history(user_id: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
  try:
    return save_ai_chat_history(user_id, messages)
  except Exception:
    return merge_ai_chat_histories(messages)


def safe_clear_ai_chat_history(user_id: str) -> None:
  try:
    clear_ai_chat_history(user_id)
  except Exception:
    pass


def guidance_to_chat_text(guidance: dict[str, Any]) -> str:
  parts = [guidance.get("summary"), guidance.get("direct_answer"), guidance.get("scholarship_note")]
  recommendations = guidance.get("top_recommendations")
  if isinstance(recommendations, list) and recommendations:
    parts.append(
      "Top recommendations: "
      + " | ".join(
        f"{item.get('programme') or 'Programme'} at {item.get('institution') or 'Institution'}: {item.get('why') or item.get('action') or 'match'}"
        for item in recommendations[:3]
        if isinstance(item, dict)
      )
    )
  study_plan = guidance.get("study_plan")
  if isinstance(study_plan, list) and study_plan:
    parts.append("Study plan: " + " | ".join(str(item) for item in study_plan[:5]))
  next_questions = guidance.get("next_questions")
  if isinstance(next_questions, list) and next_questions:
    parts.append("Next questions: " + " | ".join(str(item) for item in next_questions[:3]))
  return "\n".join(str(part) for part in parts if part).strip()[:2400] or "Guidance generated from your current EduGuide profile."


def now_iso() -> str:
  return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_iso_datetime(value: str | None) -> datetime | None:
  if not value:
    return None
  try:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
  except ValueError:
    return None


def minutes_from_now(minutes: int) -> str:
  return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat(timespec="milliseconds").replace("+00:00", "Z")


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
  email_verified_at = user.get("emailVerifiedAt") or created_at
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
    "emailVerifiedAt": email_verified_at,
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


def verification_payload_from_request(payload: AuthRegisterRequest) -> dict[str, Any]:
  password_salt, password_hash = hash_password(payload.password or "")
  return {
    "name": (payload.name or "").strip(),
    "email": normalize_email(payload.email),
    "district": (payload.district or "").strip(),
    "passwordSalt": password_salt,
    "passwordHash": password_hash,
  }


def get_latest_email_verification(email: str, purpose: str = "registration") -> dict[str, Any] | None:
  if using_supabase():
    rows = supabase_request(
      "GET",
      supabase_table_path(
        "runtime_email_verifications",
        f"email=eq.{supabase_filter_value(email)}&purpose=eq.{supabase_filter_value(purpose)}&consumed_at=is.null&order=created_at.desc&limit=1",
      ),
    )
    return rows[0] if rows else None

  with get_db_connection() as connection:
    row = connection.execute(
      """
      select * from email_verifications
      where email = ? and purpose = ? and consumed_at is null
      order by created_at desc
      limit 1
      """,
      (email, purpose),
    ).fetchone()
  return dict(row) if row else None


def consume_existing_email_verifications(email: str, purpose: str = "registration") -> None:
  timestamp = now_iso()
  if using_supabase():
    supabase_request(
      "PATCH",
      supabase_table_path(
        "runtime_email_verifications",
        f"email=eq.{supabase_filter_value(email)}&purpose=eq.{supabase_filter_value(purpose)}&consumed_at=is.null",
      ),
      {"consumed_at": timestamp},
      prefer="return=minimal",
    )
    return

  with get_db_connection() as connection:
    connection.execute(
      "update email_verifications set consumed_at = ? where email = ? and purpose = ? and consumed_at is null",
      (timestamp, email, purpose),
    )
    connection.commit()


def create_email_verification(email: str, payload: dict[str, Any], code: str, purpose: str = "registration") -> dict[str, Any]:
  latest = get_latest_email_verification(email, purpose)
  latest_created = parse_iso_datetime(str(latest.get("created_at") or "")) if latest else None
  if latest_created and datetime.now(timezone.utc) - latest_created < timedelta(seconds=EMAIL_VERIFICATION_RESEND_SECONDS):
    wait = EMAIL_VERIFICATION_RESEND_SECONDS - int((datetime.now(timezone.utc) - latest_created).total_seconds())
    raise HTTPException(status_code=429, detail=f"Please wait {max(wait, 1)} seconds before requesting another code.")

  consume_existing_email_verifications(email, purpose)
  code_salt, code_hash = hash_password(code)
  record = {
    "id": f"verify-{uuid.uuid4().hex[:16]}",
    "email": email,
    "purpose": purpose,
    "code_hash": code_hash,
    "code_salt": code_salt,
    "payload": payload,
    "attempts": 0,
    "created_at": now_iso(),
    "expires_at": minutes_from_now(EMAIL_VERIFICATION_TTL_MINUTES),
    "consumed_at": None,
  }
  if using_supabase():
    supabase_request(
      "POST",
      supabase_table_path("runtime_email_verifications"),
      record,
      prefer="return=minimal",
    )
    return record

  with get_db_connection() as connection:
    connection.execute(
      """
      insert into email_verifications
      (id, email, purpose, code_hash, code_salt, payload, attempts, created_at, expires_at, consumed_at)
      values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      """,
      (
        record["id"],
        record["email"],
        record["purpose"],
        record["code_hash"],
        record["code_salt"],
        json.dumps(record["payload"], ensure_ascii=False),
        record["attempts"],
        record["created_at"],
        record["expires_at"],
        record["consumed_at"],
      ),
    )
    connection.commit()
  return record


def update_email_verification(record_id: str, changes: dict[str, Any]) -> None:
  if using_supabase():
    supabase_request(
      "PATCH",
      supabase_table_path("runtime_email_verifications", f"id=eq.{supabase_filter_value(record_id)}"),
      changes,
      prefer="return=minimal",
    )
    return

  allowed = {key: value for key, value in changes.items() if key in {"attempts", "consumed_at"}}
  if not allowed:
    return
  assignments = ", ".join(f"{key} = ?" for key in allowed)
  values = list(allowed.values()) + [record_id]
  with get_db_connection() as connection:
    connection.execute(f"update email_verifications set {assignments} where id = ?", values)
    connection.commit()


def get_verification_payload(record: dict[str, Any]) -> dict[str, Any]:
  payload = record.get("payload")
  if isinstance(payload, dict):
    return payload
  if isinstance(payload, str):
    return parse_jsonish(payload, {})
  return {}


def verify_registration_code(email: str, code: str) -> dict[str, Any]:
  record = get_latest_email_verification(email, "registration")
  if not record:
    raise HTTPException(status_code=400, detail="No active verification code was found. Request a new code.")
  expires_at = parse_iso_datetime(str(record.get("expires_at") or ""))
  if not expires_at or expires_at < datetime.now(timezone.utc):
    update_email_verification(record["id"], {"consumed_at": now_iso()})
    raise HTTPException(status_code=400, detail="Verification code expired. Request a new code.")
  attempts = int(record.get("attempts") or 0)
  if attempts >= EMAIL_VERIFICATION_MAX_ATTEMPTS:
    update_email_verification(record["id"], {"consumed_at": now_iso()})
    raise HTTPException(status_code=400, detail="Too many incorrect attempts. Request a new code.")
  attempts += 1
  update_email_verification(record["id"], {"attempts": attempts})
  if not verify_password(code.strip(), {"passwordHash": record.get("code_hash"), "passwordSalt": record.get("code_salt")}):
    raise HTTPException(status_code=400, detail="Verification code is not correct.")
  update_email_verification(record["id"], {"consumed_at": now_iso()})
  return get_verification_payload(record)


def validate_registration_input(payload: AuthRegisterRequest) -> tuple[str, str, str, str]:
  name = (payload.name or "").strip()
  email = normalize_email(payload.email)
  password = payload.password or ""
  district = (payload.district or "").strip()
  if not name or not email or not password:
    raise HTTPException(status_code=400, detail="Name, email, and password are required.")
  if len(password) < 6:
    raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
  return name, email, password, district


def create_student_account(registration: dict[str, Any], email_verified_at: str | None = None) -> dict[str, Any]:
  name = (registration.get("name") or "").strip()
  email = normalize_email(registration.get("email"))
  password_salt = registration.get("passwordSalt")
  password_hash = registration.get("passwordHash")
  if not name or not email or not password_salt or not password_hash:
    raise HTTPException(status_code=400, detail="Verification record is incomplete. Request a new code.")
  users = get_auth_users_internal()
  if any(user["email"] == email for user in users):
    raise HTTPException(status_code=409, detail="That email already has an account.")
  timestamp = now_iso()
  user = {
    "id": f"user-{uuid.uuid4().hex[:12]}",
    "name": name,
    "email": email,
    "passwordSalt": password_salt,
    "passwordHash": password_hash,
    "role": "student",
    "status": "active",
    "district": (registration.get("district") or "").strip(),
    "stream": "",
    "leavingYear": "",
    "incomeBand": "mid",
    "needSignals": [],
    "preferenceText": "",
    "grades": {},
    "documents": [],
    "shortlist": [],
    "createdAt": timestamp,
    "emailVerifiedAt": email_verified_at or timestamp,
    "reviewedAt": None,
    "lastActiveAt": timestamp,
    "lastActivity": "Student account created",
    "activity": [],
  }
  add_user_activity(user, "account_created", "Student account created after email verification", user)
  users.append(user)
  save_auth_users_internal(users)
  return user


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
    "emailVerifiedAt": timestamp,
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
      "emailVerifiedAt": timestamp,
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


def get_session_user_id(token: str) -> str | None:
  if using_supabase():
    rows = supabase_request(
      "GET",
      supabase_table_path(
        "runtime_auth_sessions",
        f"token=eq.{supabase_filter_value(token)}&select=user_id&limit=1",
      ),
    )
    if not rows:
      return None
    supabase_request(
      "PATCH",
      supabase_table_path("runtime_auth_sessions", f"token=eq.{supabase_filter_value(token)}"),
      {"last_seen_at": now_iso()},
      prefer="return=minimal",
    )
    return rows[0].get("user_id")

  with get_db_connection() as connection:
    row = connection.execute("select user_id from auth_sessions where token = ?", (token,)).fetchone()
    if row:
      connection.execute("update auth_sessions set last_seen_at = current_timestamp where token = ?", (token,))
      connection.commit()
  return row["user_id"] if row else None


def require_current_user(authorization: str | None) -> dict[str, Any]:
  token = get_bearer_token(authorization)
  user_id = get_session_user_id(token)
  if not user_id:
    raise HTTPException(status_code=401, detail="Session expired. Please login again.")
  user = next((item for item in get_auth_users_internal() if item["id"] == user_id), None)
  if not user or user.get("status") == "suspended":
    raise HTTPException(status_code=403, detail="Account is not active.")
  return user


def require_admin_user(authorization: str | None) -> dict[str, Any]:
  user = require_current_user(authorization)
  if user.get("role") not in {"owner", "admin"}:
    raise HTTPException(status_code=403, detail="Admin access required.")
  return user


def require_user_access(target_user_id: str, authorization: str | None) -> dict[str, Any]:
  user = require_current_user(authorization)
  if user.get("role") in {"owner", "admin"} or user.get("id") == target_user_id:
    return user
  raise HTTPException(status_code=403, detail="You can only access your own records.")


def create_auth_session(user_id: str) -> str:
  token = secrets.token_urlsafe(32)
  if using_supabase():
    supabase_request(
      "POST",
      supabase_table_path("runtime_auth_sessions"),
      {"token": token, "user_id": user_id},
      prefer="return=minimal",
    )
    return token

  with get_db_connection() as connection:
    connection.execute("insert into auth_sessions (token, user_id) values (?, ?)", (token, user_id))
    connection.commit()
  return token


def delete_auth_session(token: str) -> None:
  if using_supabase():
    supabase_request(
      "DELETE",
      supabase_table_path("runtime_auth_sessions", f"token=eq.{supabase_filter_value(token)}"),
      prefer="return=minimal",
    )
    return

  with get_db_connection() as connection:
    connection.execute("delete from auth_sessions where token = ?", (token,))
    connection.commit()


def sanitize_database_state_payload(state_key: str, payload: Any) -> Any:
  if state_key != "auth_users" or not isinstance(payload, dict):
    return payload
  users = payload.get("users")
  if not isinstance(users, list):
    return payload
  cleaned_users = [public_user(user) for user in get_auth_users_internal()]
  return {**payload, "users": cleaned_users}


STARTUP_PERSISTENCE_ERROR = None
try:
  seed_bootstrap_admin()
except Exception as exc:
  STARTUP_PERSISTENCE_ERROR = str(exc)


@app.get("/api/db/state")
def get_database_state() -> dict[str, Any]:
  state = {}
  updated_at = {}
  for row in list_state_payloads():
    state_key = row.get("state_key")
    if state_key == "auth_users":
      continue
    state[state_key] = parse_jsonish(row.get("payload"), row.get("payload"))
    updated_at[state_key] = row.get("updated_at")
  return {
    "ok": True,
    "database": get_data_backend(),
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
  save_state_payload(safe_key, payload)
  return {"ok": True, "state_key": safe_key}


@app.delete("/api/db/state/{state_key}")
def delete_database_state(state_key: str) -> dict[str, Any]:
  safe_key = re.sub(r"[^a-zA-Z0-9_-]", "", state_key).strip()
  if not safe_key:
    return {"ok": False, "error": "Invalid state key"}
  deleted = delete_state_payload(safe_key)
  return {"ok": True, "state_key": safe_key, "deleted": deleted}


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


@app.post("/api/auth/register/request-code")
def auth_register_request_code(payload: AuthRegisterRequest) -> dict[str, Any]:
  seed_bootstrap_admin()
  name, email, _password, _district = validate_registration_input(payload)
  if any(user["email"] == email for user in get_auth_users_internal()):
    raise HTTPException(status_code=409, detail="That email already has an account.")

  code = f"{secrets.randbelow(1_000_000):06d}"
  record = create_email_verification(email, verification_payload_from_request(payload), code)
  try:
    send_verification_email(email, name, code)
    return {
      "ok": True,
      "email": email,
      "emailSent": True,
      "expiresInMinutes": EMAIL_VERIFICATION_TTL_MINUTES,
      "resendSeconds": EMAIL_VERIFICATION_RESEND_SECONDS,
    }
  except Exception as exc:
    if email_debug_codes_enabled():
      return {
        "ok": True,
        "email": email,
        "emailSent": False,
        "debugCode": code,
        "expiresInMinutes": EMAIL_VERIFICATION_TTL_MINUTES,
        "resendSeconds": EMAIL_VERIFICATION_RESEND_SECONDS,
        "message": f"Email delivery is not configured. Development code: {code}",
      }
    update_email_verification(record["id"], {"consumed_at": now_iso()})
    raise HTTPException(
      status_code=503,
      detail=f"Email delivery is not configured yet. Set SMTP_HOST and SMTP_FROM_EMAIL on the server. ({exc})",
    )


@app.post("/api/auth/register/verify")
def auth_register_verify(payload: AuthVerifyRegistrationRequest) -> dict[str, Any]:
  seed_bootstrap_admin()
  name, email, password, district = validate_registration_input(payload)
  if any(user["email"] == email for user in get_auth_users_internal()):
    raise HTTPException(status_code=409, detail="That email already has an account.")
  registration = verify_registration_code(email, payload.code)
  if normalize_email(registration.get("email")) != email:
    raise HTTPException(status_code=400, detail="Verification email does not match this registration.")
  if (registration.get("name") or "").strip() != name or (registration.get("district") or "").strip() != district:
    raise HTTPException(status_code=400, detail="Registration details changed. Request a new code.")
  if not verify_password(password, registration):
    raise HTTPException(status_code=400, detail="Password changed. Request a new code.")
  user = create_student_account(registration, email_verified_at=now_iso())
  return {"ok": True, "token": create_auth_session(user["id"]), "user": public_user(user)}


@app.post("/api/auth/register")
def auth_register(payload: AuthRegisterRequest) -> dict[str, Any]:
  if not payload.code:
    raise HTTPException(status_code=400, detail="Request and verify an email code before creating an account.")
  verify_payload = AuthVerifyRegistrationRequest(**payload.model_dump())
  return auth_register_verify(verify_payload)


@app.get("/api/auth/me")
def auth_me(authorization: str | None = Header(default=None)) -> dict[str, Any]:
  user = require_current_user(authorization)
  return {"ok": True, "user": public_user(user)}


@app.post("/api/auth/logout")
def auth_logout(authorization: str | None = Header(default=None)) -> dict[str, Any]:
  token = get_bearer_token(authorization)
  delete_auth_session(token)
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
async def upload_documents(user_id: str = Form(...), files: list[UploadFile] = File(...), authorization: str | None = Header(default=None)) -> dict[str, Any]:
  require_user_access(user_id, authorization)
  safe_user_id = sanitize_storage_segment(user_id, "anonymous")
  if not files:
    raise HTTPException(status_code=400, detail="No documents were uploaded.")

  saved_documents = []

  for upload in files:
    original_name = sanitize_upload_filename(upload.filename or "document")
    extension = Path(original_name).suffix.lower()
    stored_name = f"{uuid.uuid4().hex}{extension}"
    content_type = upload.content_type
    chunks: list[bytes] = []
    size = 0

    try:
      while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
          break
        size += len(chunk)
        if size > MAX_UPLOAD_BYTES:
          raise HTTPException(status_code=413, detail=f"{original_name} is larger than 10 MB.")
        chunks.append(chunk)
    finally:
      await upload.close()

    document_id = uuid.uuid4().hex
    content = b"".join(chunks)
    if using_supabase():
      storage_path = f"{safe_user_id}/{stored_name}"
      upload_supabase_storage_object(storage_path, content, content_type)
    else:
      user_folder = UPLOAD_ROOT / safe_user_id
      user_folder.mkdir(parents=True, exist_ok=True)
      destination = user_folder / stored_name
      with destination.open("wb") as output:
        output.write(content)
      storage_path = destination.relative_to(ROOT).as_posix()

    insert_document_record(
      {
        "id": document_id,
        "user_id": user_id,
        "original_name": original_name,
        "stored_name": stored_name,
        "content_type": content_type,
        "size_bytes": size,
        "storage_path": storage_path,
        "status": "Uploaded - OCR pending",
        "extraction_status": "pending",
        "extracted_grades": [],
      }
    )
    row = extract_document(document_id)
    saved_documents.append(document_response(row))

  return {"ok": True, "documents": saved_documents}


@app.get("/api/documents/user/{user_id}")
def list_user_documents(user_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
  require_user_access(user_id, authorization)
  rows = list_document_records(user_id)
  return {"ok": True, "documents": [document_response(row) for row in rows]}


@app.post("/api/documents/{document_id}/extract")
def rerun_document_extraction(document_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
  safe_document_id = sanitize_storage_segment(document_id)
  row = get_document_record(safe_document_id)
  if not row:
    raise HTTPException(status_code=404, detail="Document not found.")
  require_user_access(str(row_get(row, "user_id")), authorization)
  row = extract_document(safe_document_id)
  return {"ok": True, "document": document_response(row)}


@app.get("/api/documents/{document_id}/download")
def download_document(document_id: str, authorization: str | None = Header(default=None)) -> Response:
  safe_document_id = sanitize_storage_segment(document_id)
  row = get_document_record(safe_document_id)
  if not row:
    raise HTTPException(status_code=404, detail="Document not found.")
  require_user_access(str(row_get(row, "user_id")), authorization)
  if using_supabase():
    content = download_supabase_storage_object(str(row_get(row, "storage_path")))
    filename = sanitize_upload_filename(str(row_get(row, "original_name") or "document"))
    return Response(
      content=content,
      media_type=row_get(row, "content_type") or "application/octet-stream",
      headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

  path = ROOT / str(row_get(row, "storage_path"))
  if not path.exists():
    raise HTTPException(status_code=404, detail="Stored document file is missing.")
  return FileResponse(path, media_type=row_get(row, "content_type") or "application/octet-stream", filename=row_get(row, "original_name"))


@app.delete("/api/documents/{document_id}")
def delete_document(document_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
  safe_document_id = sanitize_storage_segment(document_id)
  existing = get_document_record(safe_document_id)
  if existing:
    require_user_access(str(row_get(existing, "user_id")), authorization)
  row = delete_document_record(safe_document_id)
  if not row:
    return {"ok": True, "deleted": 0}
  if using_supabase():
    delete_supabase_storage_object(str(row_get(row, "storage_path")))
    return {"ok": True, "deleted": 1}

  path = ROOT / str(row_get(row, "storage_path"))
  if path.exists() and UPLOAD_ROOT in path.resolve().parents:
    path.unlink(missing_ok=True)
  return {"ok": True, "deleted": 1}


@app.get("/api/db/diagnostics")
def database_diagnostics() -> dict[str, Any]:
  if using_supabase():
    state_rows = list_state_payloads()
    document_rows = supabase_request(
      "GET",
      supabase_table_path("runtime_uploaded_documents", "select=id,user_id,extraction_status&limit=10000"),
    ) or []
    run_rows = supabase_request(
      "GET",
      supabase_table_path("runtime_recommendation_runs", "select=mode,question,profile_name,created_at&order=created_at.desc&limit=5"),
    ) or []
    run_count_rows = supabase_request(
      "GET",
      supabase_table_path("runtime_recommendation_runs", "select=id&limit=10000"),
    ) or []
    try:
      chat_count_rows = supabase_request(
        "GET",
        supabase_table_path("runtime_ai_chat_messages", "select=id&limit=10000"),
      ) or []
    except Exception:
      chat_count_rows = []
    user_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    for document in document_rows:
      user_counts[str(document.get("user_id") or "unknown")] = user_counts.get(str(document.get("user_id") or "unknown"), 0) + 1
      status = str(document.get("extraction_status") or "pending")
      status_counts[status] = status_counts.get(status, 0) + 1
    document_users = [{"user_id": key, "total": value} for key, value in sorted(user_counts.items(), key=lambda item: (-item[1], item[0]))[:10]]
    extraction_statuses = [{"extraction_status": key, "total": value} for key, value in sorted(status_counts.items(), key=lambda item: (-item[1], item[0]))]
    run_count = len(run_count_rows)
    chat_message_count = len(chat_count_rows)
    document_count = len(document_rows)
    latest_runs = run_rows
  else:
    with get_db_connection() as connection:
      state_rows = [
        {
          "state_key": row["state_key"],
          "payload": parse_jsonish(row["payload"], {}),
          "updated_at": row["updated_at"],
        }
        for row in connection.execute("select state_key, payload, updated_at from app_state").fetchall()
      ]
      run_count = connection.execute("select count(*) as total from recommendation_runs").fetchone()["total"]
      chat_message_count = connection.execute("select count(*) as total from ai_chat_messages").fetchone()["total"]
      document_count = connection.execute("select count(*) as total from uploaded_documents").fetchone()["total"]
      document_users = [
        dict(row)
        for row in connection.execute(
          """
          select user_id, count(*) as total
          from uploaded_documents
          group by user_id
          order by total desc, user_id
          limit 10
          """
        ).fetchall()
      ]
      extraction_statuses = [
        dict(row)
        for row in connection.execute(
          """
          select extraction_status, count(*) as total
          from uploaded_documents
          group by extraction_status
          order by total desc, extraction_status
          """
        ).fetchall()
      ]
      latest_runs = [
        dict(row)
        for row in connection.execute(
          """
          select mode, question, profile_name, created_at
          from recommendation_runs
          order by id desc
          limit 5
          """
        ).fetchall()
      ]
  state_counts = {}
  for row in state_rows:
    payload = parse_jsonish(row.get("payload"), {})
    state_key = row.get("state_key")
    if state_key == "auth_users":
      state_counts[state_key] = len(payload.get("users", [])) if isinstance(payload, dict) else 0
    elif state_key == "review_state" and isinstance(payload, dict):
      state_counts[state_key] = {
        "programmes": len(payload.get("programmeStatuses", {})),
        "edits": len(payload.get("programmeEdits", {})),
        "gaps": len(payload.get("gapStatuses", {})),
      }
    else:
      state_counts[state_key] = 1
  return {
    "ok": True,
    "database": get_data_backend(),
    "supabase_configured": supabase_configured(),
    "storage_bucket": get_supabase_storage_bucket() if using_supabase() else None,
    "startup_persistence_error": STARTUP_PERSISTENCE_ERROR,
    "state_keys": [row.get("state_key") for row in state_rows],
    "state_counts": state_counts,
    "document_count": document_count,
    "documents_by_user": document_users,
    "document_extraction_statuses": extraction_statuses,
    "recommendation_run_count": run_count,
    "ai_chat_message_count": chat_message_count,
    "latest_runs": latest_runs,
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
  database_ready = check_data_backend_ready()
  storage_ready = check_document_storage_ready()
  return {
    "ok": database_ready and storage_ready and not STARTUP_PERSISTENCE_ERROR,
    "data_backend": get_data_backend(),
    "provider": provider,
    "ai_configured": bool(get_gemini_api_key() if provider == "gemini" else get_openai_api_key()),
    "gemini_configured": bool(get_gemini_api_key()),
    "openai_configured": bool(get_openai_api_key()),
    "email_configured": smtp_configured(),
    "email_debug_codes": email_debug_codes_enabled(),
    "database_ready": database_ready,
    "storage_ready": storage_ready,
    "supabase_configured": supabase_configured(),
    "storage_bucket": get_supabase_storage_bucket() if using_supabase() else None,
    "startup_persistence_error": STARTUP_PERSISTENCE_ERROR,
    "model": get_gemini_model_candidates()[0] if provider == "gemini" else os.getenv("OPENAI_MODEL", "gpt-5.2"),
  }


@app.get("/api/ai/chat")
def ai_chat_history(authorization: str | None = Header(default=None)) -> dict[str, Any]:
  user = require_current_user(authorization)
  return {"ok": True, "messages": safe_list_ai_chat_history(user["id"])}


@app.delete("/api/ai/chat")
def ai_chat_clear(authorization: str | None = Header(default=None)) -> dict[str, Any]:
  user = require_current_user(authorization)
  safe_clear_ai_chat_history(user["id"])
  users = get_auth_users_internal()
  stored = next((item for item in users if item["id"] == user["id"]), None)
  if stored:
    add_user_activity(stored, "ai_chat_cleared", "Cleared EduGuide AI chat", user)
    save_auth_users_internal(users)
  return {"ok": True, "messages": []}


@app.post("/api/ai/guidance")
def ai_guidance(payload: GuidanceRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
  if not payload.matches and not payload.blockedMatches:
    return {
      "mode": "local_fallback",
      "model": None,
      "guidance": build_fallback(payload, "No matches were sent to the AI endpoint."),
    }

  current_user = require_current_user(authorization) if authorization else None
  incoming_history = merge_ai_chat_histories(payload.conversation)
  server_history = safe_list_ai_chat_history(current_user["id"]) if current_user else []
  merged_history = merge_ai_chat_histories(server_history, incoming_history)
  request_payload = build_request_payload(payload, merged_history)
  save_recommendation_run(payload, request_payload)
  if get_ai_provider() == "openai":
    result = call_openai(payload, request_payload)
  else:
    result = call_gemini(payload, request_payload)

  if current_user:
    guidance = result.get("guidance") if isinstance(result, dict) else {}
    assistant_message = {
      "id": f"ai-{uuid.uuid4().hex[:12]}",
      "role": "assistant",
      "content": guidance_to_chat_text(guidance if isinstance(guidance, dict) else {}),
      "at": now_iso(),
    }
    chat = safe_save_ai_chat_history(current_user["id"], [*merged_history, assistant_message])
    users = get_auth_users_internal()
    stored = next((item for item in users if item["id"] == current_user["id"]), None)
    if stored:
      add_user_activity(stored, "ai_guidance", "Used EduGuide AI", current_user, {"mode": payload.mode})
      save_auth_users_internal(users)
    result["chat"] = chat
  return result


@app.get("/")
def index() -> FileResponse:
  return cached_file_response(ROOT / "index.html", media_type="text/html", headers=NO_CACHE_HEADERS)


@app.get("/index.html")
def index_html() -> FileResponse:
  return cached_file_response(ROOT / "index.html", media_type="text/html", headers=NO_CACHE_HEADERS)


@app.get("/styles.css")
def styles() -> FileResponse:
  return cached_file_response(ROOT / "styles.css", media_type="text/css")


@app.get("/app.js")
def app_script() -> FileResponse:
  return cached_file_response(ROOT / "app.js", media_type="application/javascript")


@app.get("/manifest.webmanifest")
def web_manifest() -> FileResponse:
  return cached_file_response(ROOT / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js")
def service_worker() -> FileResponse:
  return cached_file_response(ROOT / "sw.js", media_type="application/javascript", headers=NO_CACHE_HEADERS)


@app.get("/icons/{file_name}")
def public_icon(file_name: str) -> FileResponse:
  if file_name not in PUBLIC_ICON_FILES:
    raise HTTPException(status_code=404, detail="Icon is not public.")
  path = ROOT / "icons" / file_name
  if not path.exists():
    raise HTTPException(status_code=404, detail="Icon not found.")
  return cached_file_response(path, media_type=guess_mime_type(path), headers=IMMUTABLE_CACHE_HEADERS)


@app.get("/data/{file_name}")
def public_data_file(file_name: str) -> FileResponse:
  if file_name not in PUBLIC_DATA_FILES:
    raise HTTPException(status_code=404, detail="File is not public.")
  path = ROOT / "data" / file_name
  if not path.exists():
    raise HTTPException(status_code=404, detail="File not found.")
  media_type = "application/javascript" if file_name.endswith(".js") else "application/json"
  return cached_file_response(path, media_type=media_type)
