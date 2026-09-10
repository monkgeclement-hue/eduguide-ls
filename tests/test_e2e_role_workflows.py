import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import server


class EndToEndRoleWorkflowTests(unittest.TestCase):
  """Exercise real HTTP role flows against a disposable SQLite database."""

  def setUp(self):
    self.tempdir = tempfile.TemporaryDirectory()
    self.original_db_path = server.DB_PATH
    self.original_upload_root = server.UPLOAD_ROOT
    self.sqlite_backend = patch.object(server, "using_supabase", return_value=False)
    self.bootstrap_admin = patch.object(server, "seed_bootstrap_admin")
    self.sqlite_backend.start()
    self.bootstrap_admin.start()
    server.DB_PATH = Path(self.tempdir.name) / "eduguide-test.db"
    server.UPLOAD_ROOT = Path(self.tempdir.name) / "uploads"
    server.RATE_LIMIT_STATE.clear()
    server.init_database()
    server.save_auth_users_internal([
      self.make_user("owner-1", "Owner", "owner@eduguide.test", "owner"),
      self.make_user("student-1", "Student One", "student1@eduguide.test", "student"),
      self.make_user("student-2", "Student Two", "student2@eduguide.test", "student"),
      self.make_user("counsellor-1", "Counsellor", "counsellor@eduguide.test", "counsellor"),
      self.make_user("institution-a", "Institution A", "a@institution.test", "institution_admin", "Example University"),
      self.make_user("institution-b", "Institution B", "b@institution.test", "institution_admin", "Another University"),
    ])
    self.client = TestClient(server.app)

  def tearDown(self):
    self.client.close()
    server.RATE_LIMIT_STATE.clear()
    server.DB_PATH = self.original_db_path
    server.UPLOAD_ROOT = self.original_upload_root
    self.bootstrap_admin.stop()
    self.sqlite_backend.stop()
    self.tempdir.cleanup()

  @staticmethod
  def make_user(user_id, name, email, role, managed_institution=""):
    password_salt, password_hash = server.hash_password("RoleTestPass1")
    timestamp = server.now_iso()
    return {
      "id": user_id,
      "name": name,
      "email": email,
      "passwordSalt": password_salt,
      "passwordHash": password_hash,
      "role": role,
      "managedInstitution": managed_institution,
      "status": "active",
      "district": "Maseru",
      "grades": {},
      "documents": [],
      "shortlist": [],
      "shortlistPathways": {},
      "applicationProgress": {},
      "applicationNotes": {},
      "applicationRecords": {},
      "createdAt": timestamp,
      "emailVerifiedAt": timestamp,
      "lastActiveAt": timestamp,
      "lastActivity": "Account created",
      "activity": [],
    }

  def login_headers(self, email):
    response = self.client.post("/api/auth/login", json={"email": email, "password": "RoleTestPass1"})
    self.assertEqual(response.status_code, 200, response.text)
    return {"Authorization": f"Bearer {response.json()['token']}"}

  def test_student_consent_controls_counsellor_visibility_end_to_end(self):
    admin_headers = self.login_headers("owner@eduguide.test")
    student_headers = self.login_headers("student1@eduguide.test")
    counsellor_headers = self.login_headers("counsellor@eduguide.test")

    assigned = self.client.post(
      "/api/admin/counsellor-assignments",
      headers=admin_headers,
      json={"counsellorId": "counsellor-1", "studentId": "student-1"},
    )
    self.assertEqual(assigned.status_code, 200, assigned.text)
    assignment_id = assigned.json()["assignment"]["id"]

    self.assertEqual(self.client.get("/api/counsellor/dashboard", headers=counsellor_headers).json()["students"], [])
    self.assertEqual(self.client.get("/api/counsellor/students/student-1", headers=counsellor_headers).status_code, 403)

    pending_access = self.client.get("/api/student/counsellor-access", headers=student_headers)
    self.assertEqual(pending_access.status_code, 200, pending_access.text)
    self.assertEqual(pending_access.json()["assignments"][0]["consentStatus"], "pending")

    granted = self.client.put(
      f"/api/student/counsellor-access/{assignment_id}",
      headers=student_headers,
      json={"consentStatus": "granted"},
    )
    self.assertEqual(granted.status_code, 200, granted.text)

    dashboard = self.client.get("/api/counsellor/dashboard", headers=counsellor_headers)
    self.assertEqual(dashboard.status_code, 200, dashboard.text)
    self.assertEqual([student["id"] for student in dashboard.json()["students"]], ["student-1"])

    followup = self.client.post(
      "/api/counsellor/followups",
      headers=counsellor_headers,
      json={"studentId": "student-1", "title": "Upload certified results", "dueAt": "2026-10-01"},
    )
    self.assertEqual(followup.status_code, 200, followup.text)
    student_access = self.client.get("/api/student/counsellor-access", headers=student_headers)
    self.assertEqual([item["title"] for item in student_access.json()["followups"]], ["Upload certified results"])

    paused = self.client.put(
      f"/api/student/counsellor-access/{assignment_id}",
      headers=student_headers,
      json={"consentStatus": "paused"},
    )
    self.assertEqual(paused.status_code, 200, paused.text)
    self.assertEqual(self.client.get("/api/counsellor/dashboard", headers=counsellor_headers).json()["students"], [])
    self.assertEqual(self.client.get("/api/counsellor/students/student-1", headers=counsellor_headers).status_code, 403)

  def test_institution_proposals_are_scoped_and_admin_review_is_visible(self):
    admin_headers = self.login_headers("owner@eduguide.test")
    institution_a_headers = self.login_headers("a@institution.test")
    institution_b_headers = self.login_headers("b@institution.test")

    created = self.client.post(
      "/api/institution/proposals",
      headers=institution_a_headers,
      json={
        "programmeId": "example-computing",
        "programmeName": "Bachelor of Computing",
        "institution": "Example University",
        "changes": {"applicationDeadline": "Applications close 31 October 2026."},
      },
    )
    self.assertEqual(created.status_code, 200, created.text)
    proposal_id = created.json()["proposal"]["id"]

    forbidden = self.client.post(
      "/api/institution/proposals",
      headers=institution_b_headers,
      json={
        "programmeId": "example-computing",
        "institution": "Example University",
        "changes": {"applicationDeadline": "Forged deadline"},
      },
    )
    self.assertEqual(forbidden.status_code, 403)
    self.assertEqual(self.client.get("/api/institution/proposals", headers=institution_b_headers).json()["proposals"], [])

    decision = self.client.put(
      f"/api/institution/proposals/{proposal_id}",
      headers=admin_headers,
      json={"status": "changes_requested", "note": "Attach the current prospectus page."},
    )
    self.assertEqual(decision.status_code, 200, decision.text)

    visible = self.client.get("/api/institution/proposals", headers=institution_a_headers)
    self.assertEqual(visible.status_code, 200, visible.text)
    proposal = visible.json()["proposals"][0]
    self.assertEqual(proposal["status"], "changes_requested")
    self.assertEqual(proposal["reviewNote"], "Attach the current prospectus page.")

  def test_source_feedback_is_private_and_tracks_admin_resolution(self):
    admin_headers = self.login_headers("owner@eduguide.test")
    student_headers = self.login_headers("student1@eduguide.test")
    other_student_headers = self.login_headers("student2@eduguide.test")

    submitted = self.client.post(
      "/api/events",
      headers=student_headers,
      json={
        "eventType": "source_outdated_reported",
        "label": "Reported a potentially outdated programme source",
        "payload": {"programmeId": "example-computing", "programmeName": "Bachelor of Computing", "institution": "Example University"},
      },
    )
    self.assertEqual(submitted.status_code, 200, submitted.text)
    report_id = submitted.json()["eventId"]

    self.assertEqual(self.client.get("/api/student/source-reports", headers=other_student_headers).json()["reports"], [])
    open_report = self.client.get("/api/student/source-reports", headers=student_headers)
    self.assertEqual(open_report.status_code, 200, open_report.text)
    self.assertEqual(open_report.json()["reports"][0]["status"], "open")

    review_state = self.client.put(
      "/api/db/state/review_state",
      headers=admin_headers,
      json={"payload": {"sourceReportResolutions": {report_id: {"status": "resolved", "reviewedAt": "2026-09-10T12:00:00Z"}}}},
    )
    self.assertEqual(review_state.status_code, 200, review_state.text)
    resolved_report = self.client.get("/api/student/source-reports", headers=student_headers)
    self.assertEqual(resolved_report.json()["reports"][0]["status"], "resolved")

  @patch.object(server, "send_verification_email")
  @patch.object(server.secrets, "randbelow", return_value=123456)
  def test_registration_requires_email_verification_before_creating_a_student(self, _random_code, send_email):
    payload = {
      "name": "Verified Student",
      "email": "verified@eduguide.test",
      "password": "VerifiedPass1",
      "district": "Maseru",
    }

    requested = self.client.post("/api/auth/register/request-code", json=payload)
    self.assertEqual(requested.status_code, 200, requested.text)
    self.assertTrue(requested.json()["emailSent"])
    send_email.assert_called_once_with("verified@eduguide.test", "Verified Student", "123456")

    before_verification = self.client.post(
      "/api/auth/login",
      json={"email": payload["email"], "password": payload["password"]},
    )
    self.assertEqual(before_verification.status_code, 401)

    verified = self.client.post("/api/auth/register/verify", json={**payload, "code": "123456"})
    self.assertEqual(verified.status_code, 200, verified.text)
    self.assertEqual(verified.json()["user"]["role"], "student")
    self.assertTrue(verified.json()["user"]["emailVerifiedAt"])

    authenticated = self.client.get(
      "/api/auth/me",
      headers={"Authorization": f"Bearer {verified.json()['token']}"},
    )
    self.assertEqual(authenticated.status_code, 200, authenticated.text)
    self.assertEqual(authenticated.json()["user"]["email"], payload["email"])

  @patch.object(server, "send_password_reset_email")
  @patch.object(server.secrets, "randbelow", return_value=654321)
  def test_password_reset_invalidates_existing_sessions_end_to_end(self, _random_code, send_email):
    old_token = self.client.post(
      "/api/auth/login",
      json={"email": "student1@eduguide.test", "password": "RoleTestPass1"},
    ).json()["token"]

    requested = self.client.post("/api/auth/password-reset/request-code", json={"email": "student1@eduguide.test"})
    self.assertEqual(requested.status_code, 200, requested.text)
    self.assertTrue(requested.json()["emailSent"])
    send_email.assert_called_once_with("student1@eduguide.test", "Student One", "654321")

    reset = self.client.post(
      "/api/auth/password-reset/confirm",
      json={"email": "student1@eduguide.test", "code": "654321", "password": "NewSecurePass2"},
    )
    self.assertEqual(reset.status_code, 200, reset.text)
    new_token = reset.json()["token"]

    self.assertEqual(
      self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_token}"}).status_code,
      401,
    )
    self.assertEqual(
      self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_token}"}).status_code,
      200,
    )
    self.assertEqual(
      self.client.post(
        "/api/auth/login",
        json={"email": "student1@eduguide.test", "password": "RoleTestPass1"},
      ).status_code,
      401,
    )
    self.assertEqual(
      self.client.post(
        "/api/auth/login",
        json={"email": "student1@eduguide.test", "password": "NewSecurePass2"},
      ).status_code,
      200,
    )

  def test_temporary_sqlite_database_is_released_after_role_requests(self):
    self.login_headers("student1@eduguide.test")
    database_path = server.DB_PATH
    with server.get_db_connection() as connection:
      self.assertEqual(connection.execute("select 1").fetchone()[0], 1)
    database_path.unlink()
    self.assertFalse(database_path.exists())


if __name__ == "__main__":
  unittest.main()
