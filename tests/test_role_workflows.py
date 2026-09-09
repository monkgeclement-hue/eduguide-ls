import unittest
from unittest.mock import patch
from datetime import datetime, timezone

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


if __name__ == "__main__":
  unittest.main(verbosity=2)
