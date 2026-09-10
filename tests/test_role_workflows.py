import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException

import server


class RoleWorkflowTests(unittest.TestCase):
  def test_counsellor_requires_granted_active_assignment(self):
    assignment = {
      "id": "assignment-1",
      "counsellorId": "counsellor-1",
      "studentId": "student-1",
      "status": "active",
      "consentStatus": "pending",
    }
    with patch.object(server, "get_counsellor_state", return_value=[assignment]):
      self.assertFalse(server.counsellor_has_student_access("counsellor-1", "student-1"))
      assignment["consentStatus"] = "granted"
      self.assertTrue(server.counsellor_has_student_access("counsellor-1", "student-1"))
      assignment["consentStatus"] = "paused"
      self.assertFalse(server.counsellor_has_student_access("counsellor-1", "student-1"))

  def test_only_assigned_counsellor_can_open_student_record(self):
    with patch.object(server, "require_counsellor_user", return_value={"id": "counsellor-1", "role": "counsellor"}), patch.object(
      server, "counsellor_has_student_access", return_value=False
    ):
      with self.assertRaises(HTTPException) as error:
        server.require_counsellor_student_access("student-1", "Bearer test")
    self.assertEqual(error.exception.status_code, 403)

  def test_new_institution_programme_needs_evidence(self):
    incomplete = {
      "id": "proposal-1",
      "programmeId": "new-1",
      "institution": "Example University",
      "proposalType": "new_programme",
      "changes": {
        "name": "Bachelor of Example Studies",
        "level": "Degree",
        "requirementsSummary": "Five credits including English.",
      },
    }
    self.assertIsNone(server.normalize_institution_proposal(incomplete))
    incomplete["changes"]["sourceUrl"] = "https://example.edu/programmes/example-studies"
    self.assertEqual(server.normalize_institution_proposal(incomplete)["proposalType"], "new_programme")

  def test_institution_application_updates_keep_only_safe_apply_links(self):
    changes = server.sanitize_institution_proposal_changes({
      "applicationUrl": "javascript:alert('unsafe')",
      "applicationDeadline": "Applications close 31 October 2026.",
      "intakeStatus": "Open for the 2027 intake.",
    })
    self.assertNotIn("applicationUrl", changes)
    self.assertEqual(changes["applicationDeadline"], "Applications close 31 October 2026.")
    self.assertEqual(changes["intakeStatus"], "Open for the 2027 intake.")

    changes = server.sanitize_institution_proposal_changes({"applicationUrl": "https://example.edu/apply"})
    self.assertEqual(changes["applicationUrl"], "https://example.edu/apply")

  def test_institution_application_document_list_is_sanitized(self):
    changes = server.sanitize_institution_proposal_changes({
      "applicationDocuments": ["National ID", "", "  COSC certificate  ", "x" * 200],
    })
    self.assertEqual(changes["applicationDocuments"][:2], ["National ID", "COSC certificate"])
    self.assertEqual(len(changes["applicationDocuments"][2]), 160)

  def test_institution_can_request_removal_of_application_documents(self):
    changes = server.sanitize_institution_proposal_changes({"applicationDocuments": []})
    self.assertEqual(changes, {"applicationDocuments": []})

  def test_institution_admin_cannot_submit_for_another_institution(self):
    actor = {
      "id": "institution-1",
      "name": "Institution Admin",
      "email": "admin@example.edu",
      "role": "institution_admin",
      "managedInstitution": "Example University",
    }
    with patch.object(server, "check_rate_limit"), patch.object(server, "require_institution_user", return_value=actor):
      with self.assertRaises(HTTPException) as error:
        server.create_institution_proposal(
          server.InstitutionProposalRequest(
            programmeId="programme-1",
            institution="Another University",
            changes={"applicationDeadline": "31 October 2026"},
          ),
          object(),
        )
    self.assertEqual(error.exception.status_code, 403)

  def test_institution_proposal_visibility_is_scoped_to_managed_school(self):
    proposals = [
      {"id": "example", "institution": "Example University"},
      {"id": "other", "institution": "Another University"},
    ]
    institution_admin = {"role": "institution_admin", "managedInstitution": "Example University"}
    self.assertEqual(
      [proposal["id"] for proposal in server.get_visible_institution_proposals(institution_admin, proposals)],
      ["example"],
    )
    admin = {"role": "admin"}
    self.assertEqual(
      [proposal["id"] for proposal in server.get_visible_institution_proposals(admin, proposals)],
      ["example", "other"],
    )

  def test_public_user_never_exposes_password_material(self):
    user = {
      "id": "student-1",
      "email": "student@example.edu",
      "password": "plain-text-legacy-value",
      "passwordHash": "hash",
      "passwordSalt": "salt",
    }
    public = server.public_user(user)
    self.assertEqual(public["id"], "student-1")
    self.assertNotIn("password", public)
    self.assertNotIn("passwordHash", public)
    self.assertNotIn("passwordSalt", public)

  def test_login_creates_a_server_session_for_valid_credentials(self):
    password_salt, password_hash = server.hash_password("StudentPass1")
    user = {
      "id": "student-1",
      "name": "Student",
      "email": "student@example.edu",
      "passwordSalt": password_salt,
      "passwordHash": password_hash,
      "role": "student",
      "status": "active",
      "activity": [],
    }
    with patch.object(server, "maybe_cleanup_security_records"), patch.object(server, "check_rate_limit"), patch.object(
      server, "seed_bootstrap_admin"
    ), patch.object(server, "get_auth_users_internal", return_value=[user]), patch.object(server, "save_auth_users_internal"), patch.object(
      server, "safe_insert_runtime_event"
    ), patch.object(server, "create_auth_session", return_value="session-token"), patch.object(server, "get_request_ip", return_value="127.0.0.1"):
      result = server.auth_login(server.AuthLoginRequest(email="student@example.edu", password="StudentPass1"), object())
    self.assertEqual(result["token"], "session-token")
    self.assertEqual(result["user"]["id"], "student-1")
    self.assertNotIn("passwordHash", result["user"])

  def test_login_ui_has_email_creation_and_live_server_feedback(self):
    root = Path(__file__).resolve().parents[1]
    index = (root / "index.html").read_text(encoding="utf-8")
    app_script = (root / "app.js").read_text(encoding="utf-8")
    self.assertIn("https://accounts.google.com/signup", index)
    self.assertIn('id="auth-connection"', index)
    self.assertIn('id="login-submit-button"', index)
    self.assertIn("function refreshAuthConnectionStatus", app_script)
    self.assertIn('fetch("/health", { cache: "no-store" })', app_script)
    self.assertIn("function setLoginSubmitBusy", app_script)

  def test_historical_reference_documents_are_allowlisted(self):
    response = server.public_reference_document("che-list-of-accredited-programmes-december-2017.pdf")
    self.assertTrue(str(response.path).endswith("che-list-of-accredited-programmes-december-2017.pdf"))
    with self.assertRaises(HTTPException) as error:
      server.public_reference_document("../../server.py")
    self.assertEqual(error.exception.status_code, 404)

  def test_historical_candidates_need_current_evidence_before_approval(self):
    candidate_id = next(iter(server.get_historical_candidate_ids()))
    incomplete_state = {
      "programmeStatuses": {candidate_id: "approved"},
      "programmeEdits": {candidate_id: {"reviewStatus": "approved"}},
    }
    with self.assertRaises(HTTPException) as error:
      server.sanitize_database_state_payload("review_state", incomplete_state)
    self.assertEqual(error.exception.status_code, 400)
    self.assertIn("current official source URL", error.exception.detail)

    reviewed_state = {
      "programmeStatuses": {candidate_id: "approved"},
      "programmeEdits": {
        candidate_id: {
          "reviewStatus": "approved",
          "sourceUrl": "https://example.edu/programmes/current-offering",
          "requirementsSummary": "Five credits including English.",
        }
      },
    }
    self.assertEqual(server.sanitize_database_state_payload("review_state", reviewed_state), reviewed_state)

  def test_historical_candidate_approval_guard_is_visible_to_admins(self):
    app_script = (Path(__file__).resolve().parents[1] / "app.js").read_text(encoding="utf-8")
    self.assertIn("function getProgrammeApprovalBlocker", app_script)
    self.assertIn("Historical CHE candidate", app_script)
    self.assertIn("historical_candidates", app_script)

  def test_browser_has_no_direct_supabase_write_path(self):
    root = Path(__file__).resolve().parents[1]
    app_script = (root / "app.js").read_text(encoding="utf-8")
    index = (root / "index.html").read_text(encoding="utf-8")
    service_worker = (root / "sw.js").read_text(encoding="utf-8")
    self.assertNotIn("supabaseClient", app_script)
    self.assertNotIn("EDUGUIDE_SUPABASE_CONFIG", app_script)
    self.assertNotIn("supabase-js", index)
    self.assertNotIn("supabase-config", index)
    self.assertNotIn("supabase-config", service_worker)
    with self.assertRaises(HTTPException) as error:
      server.public_data_file("supabase-config.js")
    self.assertEqual(error.exception.status_code, 404)

  def test_students_cannot_write_privileged_audit_events(self):
    student = {"id": "student-1", "role": "student"}
    event = server.RuntimeEventRequest(eventType="admin_programme_approved", label="Forged admin event")
    with patch.object(server, "require_current_user", return_value=student), patch.object(server, "check_rate_limit"):
      with self.assertRaises(HTTPException) as error:
        server.record_runtime_event(event, None, "Bearer test")
    self.assertEqual(error.exception.status_code, 403)

  def test_admin_can_write_privileged_audit_events(self):
    admin = {"id": "admin-1", "role": "admin"}
    event = server.RuntimeEventRequest(eventType="admin_programme_approved", label="Approved programme")
    saved = {"id": "evt-1"}
    with patch.object(server, "require_current_user", return_value=admin), patch.object(server, "check_rate_limit"), patch.object(
      server, "insert_runtime_event", return_value=saved
    ):
      result = server.record_runtime_event(event, None, "Bearer test")
    self.assertEqual(result, {"ok": True, "eventId": "evt-1"})

  def test_student_source_feedback_is_included_in_the_admin_audit(self):
    self.assertTrue(server.is_audit_event("source_outdated_reported"))
    self.assertFalse(server.is_audit_event("profile_updated"))
    event = {
      "id": "evt-source",
      "user_id": "student-1",
      "event_type": "source_outdated_reported",
      "label": "Reported a potentially outdated programme source",
      "created_at": server.now_iso(),
      "payload": {"programmeId": "programme-1", "institution": "Example University"},
    }
    with patch.object(server, "safe_list_runtime_events", return_value=[event]), patch.object(
      server, "get_auth_users_internal", return_value=[{"id": "student-1", "name": "Student", "email": "student@example.edu", "role": "student"}]
    ):
      audit = server.build_admin_audit_log()
    self.assertEqual(audit[0]["id"], "evt-source")
    self.assertEqual(audit[0]["eventType"], "source_outdated_reported")

  def test_source_report_resolution_state_is_sanitized(self):
    state = server.sanitize_database_state_payload(
      "review_state",
      {
        "sourceReportResolutions": {
          "evt-123": {"status": "resolved", "reviewedAt": "2026-09-10T12:00:00Z", "ignored": "value"},
          "evt-456": {"status": "open"},
          "bad id!": {"status": "in_progress"},
        }
      },
    )
    self.assertEqual(
      state["sourceReportResolutions"],
      {
        "evt-123": {"status": "resolved", "reviewedAt": "2026-09-10T12:00:00Z"},
      },
    )

  def test_source_reports_have_an_admin_queue_and_server_persistence(self):
    app_script = (Path(__file__).resolve().parents[1] / "app.js").read_text(encoding="utf-8")
    self.assertIn("function getFilteredAdminSourceReports", app_script)
    self.assertIn("function setSourceReportStatus", app_script)
    self.assertIn("data-source-report-status", app_script)
    self.assertIn("sourceUrl: programme?.sourceUrl", app_script)

  def test_student_source_reports_are_scoped_and_include_review_status(self):
    student = {"id": "student-1", "role": "student"}
    events = [
      {
        "id": "evt-mine",
        "user_id": "student-1",
        "event_type": "source_outdated_reported",
        "created_at": "2026-09-10T10:00:00Z",
        "payload": {"programmeId": "programme-1", "programmeName": "Bachelor of Example", "institution": "Example University"},
      },
      {
        "id": "evt-other",
        "user_id": "student-2",
        "event_type": "source_outdated_reported",
        "created_at": "2026-09-10T09:00:00Z",
        "payload": {"programmeName": "Private report"},
      },
    ]
    review_state = {"sourceReportResolutions": {"evt-mine": {"status": "resolved", "reviewedAt": "2026-09-10T11:00:00Z"}}}
    with patch.object(server, "require_current_user", return_value=student), patch.object(server, "check_rate_limit"), patch.object(
      server, "safe_list_runtime_events", return_value=events
    ), patch.object(server, "load_state_payload", return_value=review_state):
      result = server.student_source_reports(object(), "Bearer test")
    self.assertEqual(result["reports"], [{
      "id": "evt-mine",
      "programmeId": "programme-1",
      "programmeName": "Bachelor of Example",
      "institution": "Example University",
      "status": "resolved",
      "createdAt": "2026-09-10T10:00:00Z",
      "reviewedAt": "2026-09-10T11:00:00Z",
    }])

  def test_student_source_report_profile_contract_is_present(self):
    root = Path(__file__).resolve().parents[1]
    index = (root / "index.html").read_text(encoding="utf-8")
    app_script = (root / "app.js").read_text(encoding="utf-8")
    self.assertIn('id="student-source-reports"', index)
    self.assertIn("function loadStudentSourceReports", app_script)
    self.assertIn('fetch("/api/student/source-reports"', app_script)
    self.assertIn('await recordCurrentUserActivity("source_outdated_reported"', app_script)

  def test_source_links_are_validated_before_they_are_rendered(self):
    app_script = (Path(__file__).resolve().parents[1] / "app.js").read_text(encoding="utf-8")
    self.assertIn("const sourceUrl = getSafeExternalUrl(source.url);", app_script)
    self.assertIn("const courseSourceUrl = getSafeExternalUrl(programme.sourceUrl);", app_script)
    self.assertIn("getSafeExternalUrl(source.url || source.sourceUrl || source.path)", app_script)

  def test_application_fields_are_kept_in_review_state_snapshots(self):
    app_script = (Path(__file__).resolve().parents[1] / "app.js").read_text(encoding="utf-8")
    persist_fields = app_script.split("const programmePersistFields = [", 1)[1].split("];", 1)[0]
    for field in ["applicationUrl", "applicationDeadline", "intakeStatus", "applicationDocuments"]:
      self.assertIn(f'"{field}"', persist_fields)
    self.assertIn("function getProgrammeApplicationDetails", app_script)
    self.assertIn("Needs application details", app_script)
    self.assertIn("confirmedCategories.has(item.category)", app_script)

  def test_programme_apply_link_is_prioritised_over_a_general_institution_link(self):
    app_script = (Path(__file__).resolve().parents[1] / "app.js").read_text(encoding="utf-8")
    link_pack = app_script.split("function getApplicationLinkPack", 1)[1].split("function normalizeFeeText", 1)[0]
    self.assertIn("const directProgrammeApplicationLinks", link_pack)
    self.assertIn("const applicationLink = directProgrammeApplicationLinks[0]", link_pack)

  def test_change_request_requires_feedback_and_locks_the_decision(self):
    proposal = {
      "id": "proposal-1",
      "programmeId": "programme-1",
      "programmeName": "Example Programme",
      "institution": "Example University",
      "proposalType": "update",
      "changes": {"overview": "Updated overview."},
      "note": "",
      "status": "pending_admin_review",
      "requestedBy": {},
      "reviewedBy": {},
      "reviewNote": "",
      "createdAt": server.now_iso(),
      "updatedAt": server.now_iso(),
    }
    admin = {"id": "admin-1", "name": "Admin", "email": "admin@example.com", "role": "admin"}
    with patch.object(server, "check_rate_limit"), patch.object(server, "require_admin_user", return_value=admin), patch.object(
      server, "load_institution_proposals", return_value=[proposal]
    ), patch.object(server, "save_institution_proposals"), patch.object(server, "safe_insert_runtime_event"), patch.object(
      server, "get_request_ip", return_value="127.0.0.1"
    ):
      with self.assertRaises(HTTPException) as missing_note:
        server.decide_institution_proposal(
          "proposal-1", server.InstitutionProposalDecisionRequest(status="changes_requested", note=""), object()
        )
      self.assertEqual(missing_note.exception.status_code, 400)

      result = server.decide_institution_proposal(
        "proposal-1",
        server.InstitutionProposalDecisionRequest(status="changes_requested", note="Attach the current prospectus page."),
        object(),
      )
      self.assertEqual(result["proposal"]["status"], "changes_requested")

      with self.assertRaises(HTTPException) as completed_review:
        server.decide_institution_proposal(
          "proposal-1", server.InstitutionProposalDecisionRequest(status="approved", note=""), object()
        )
      self.assertEqual(completed_review.exception.status_code, 409)

  def test_new_programme_revision_links_only_to_requested_changes(self):
    prior = {
      "id": "proposal-prior",
      "programmeId": "new-prior",
      "programmeName": "Bachelor of Example Studies",
      "institution": "Example University",
      "proposalType": "new_programme",
      "changes": {
        "name": "Bachelor of Example Studies",
        "level": "Degree",
        "requirementsSummary": "Five credits including English.",
        "sourceUrl": "https://example.edu/prospectus",
      },
      "note": "Official prospectus.",
      "status": "changes_requested",
      "requestedBy": {},
      "reviewedBy": {},
      "reviewNote": "Add the current programme duration.",
      "createdAt": server.now_iso(),
      "updatedAt": server.now_iso(),
    }
    actor = {"id": "institution-1", "name": "Institution Admin", "email": "admin@example.edu", "role": "institution_admin", "managedInstitution": "Example University"}
    submitted = []
    with patch.object(server, "check_rate_limit"), patch.object(server, "require_institution_user", return_value=actor), patch.object(
      server, "load_institution_proposals", return_value=[prior]
    ), patch.object(server, "save_institution_proposals", side_effect=lambda proposals: submitted.extend(proposals)), patch.object(
      server, "safe_insert_runtime_event"), patch.object(server, "get_request_ip", return_value="127.0.0.1"):
      result = server.create_institution_proposal(
        server.InstitutionProposalRequest(
          programmeId="new-revision",
          programmeName="Bachelor of Example Studies",
          institution="Example University",
          proposalType="new_programme",
          resubmissionOf="proposal-prior",
          changes={
            "name": "Bachelor of Example Studies",
            "level": "Degree",
            "duration": "4 years",
            "requirementsSummary": "Five credits including English.",
            "sourceUrl": "https://example.edu/prospectus",
          },
        ),
        object(),
      )
    self.assertEqual(result["proposal"]["resubmissionOf"], "proposal-prior")
    self.assertEqual(submitted[0]["resubmissionOf"], "proposal-prior")

  def test_followup_due_states_prioritise_student_actions(self):
    today = datetime(2026, 9, 9, tzinfo=timezone.utc)
    self.assertEqual(server.followup_due_state({"dueAt": "2026-09-08"}, today), "overdue")
    self.assertEqual(server.followup_due_state({"dueAt": "2026-09-16"}, today), "due_soon")
    self.assertEqual(server.followup_due_state({"dueAt": "2026-09-17"}, today), "scheduled")
    self.assertEqual(server.followup_due_state({"dueAt": ""}, today), "undated")
    self.assertEqual(server.safe_followup_due_date("not-a-date"), "")

  def test_student_followups_only_include_granted_counsellors(self):
    actor = {"id": "student-1", "role": "student"}
    assignments = [
      {"id": "assignment-granted", "studentId": "student-1", "counsellorId": "counsellor-granted", "status": "active", "consentStatus": "granted"},
      {"id": "assignment-paused", "studentId": "student-1", "counsellorId": "counsellor-paused", "status": "active", "consentStatus": "paused"},
    ]
    followups = [
      {"id": "visible", "studentId": "student-1", "counsellorId": "counsellor-granted", "title": "Upload results", "dueAt": "2026-09-10", "status": "open"},
      {"id": "hidden", "studentId": "student-1", "counsellorId": "counsellor-paused", "title": "Private to paused access", "dueAt": "2026-09-10", "status": "open"},
    ]
    users = [
      {"id": "counsellor-granted", "role": "counsellor", "status": "active", "name": "Granted Counsellor"},
      {"id": "counsellor-paused", "role": "counsellor", "status": "active", "name": "Paused Counsellor"},
    ]
    def state_for(key):
      return assignments if key == server.COUNSELLOR_ASSIGNMENTS_STATE_KEY else followups

    with patch.object(server, "require_current_user", return_value=actor), patch.object(server, "check_rate_limit"), patch.object(
      server, "get_auth_users_internal", return_value=users
    ), patch.object(server, "get_counsellor_state", side_effect=state_for):
      result = server.student_counsellor_access(object(), "Bearer test")
    self.assertEqual([item["id"] for item in result["followups"]], ["visible"])

  def test_counsellor_workload_counts_only_granted_student_actions(self):
    users = [
      {"id": "counsellor-1", "name": "Counsellor One", "email": "counsellor@example.edu", "role": "counsellor", "status": "active"},
      {"id": "student-granted", "role": "student", "name": "Granted Student"},
      {"id": "student-paused", "role": "student", "name": "Paused Student"},
    ]
    assignments = [
      {"counsellorId": "counsellor-1", "studentId": "student-granted", "status": "active", "consentStatus": "granted"},
      {"counsellorId": "counsellor-1", "studentId": "student-paused", "status": "active", "consentStatus": "paused"},
    ]
    followups = [
      {"id": "overdue", "counsellorId": "counsellor-1", "studentId": "student-granted", "status": "open", "title": "Upload results", "dueAt": "2020-01-01"},
      {"id": "hidden", "counsellorId": "counsellor-1", "studentId": "student-paused", "status": "open", "title": "Do not count", "dueAt": "2020-01-01"},
    ]
    workload = server.build_counsellor_workloads(users, assignments, followups)[0]
    self.assertEqual(workload["assignedStudents"], 2)
    self.assertEqual(workload["grantedStudents"], 1)
    self.assertEqual(workload["pausedAccess"], 1)
    self.assertEqual(workload["openFollowups"], 1)
    self.assertEqual(workload["overdueFollowups"], 1)


if __name__ == "__main__":
  unittest.main(verbosity=2)
