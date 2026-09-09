import unittest
from unittest.mock import patch

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


if __name__ == "__main__":
  unittest.main(verbosity=2)
