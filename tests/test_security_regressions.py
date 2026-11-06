import os
import json
import importlib.util
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch
from copy import deepcopy
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request
import server


class SecurityRegressionTests(unittest.TestCase):
  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    self.patches = [patch.object(server, 'DB_PATH', Path(self.temp.name)/'test.db'), patch.object(server, 'using_supabase', return_value=False), patch.object(server, 'seed_bootstrap_admin')]
    for item in self.patches: item.start()
    server.init_database()
    salt, digest = server.hash_password('TestPassword1')
    server.save_auth_users_internal([{'id': key, 'email': f'{key}@example.test', 'name': key, 'role':'student', 'passwordSalt':salt, 'passwordHash':digest} for key in ['a','b']])
    self.client = TestClient(server.app)

  def tearDown(self):
    self.client.close()
    for item in reversed(self.patches): item.stop()
    self.temp.cleanup()

  def test_interleaved_students_keep_both_edits(self):
    first, second = server.get_auth_users_internal(), server.get_auth_users_internal()
    first[0]['name']='Changed A'
    second[1]['name']='Changed B'
    server.save_auth_users_internal(first)
    server.save_auth_users_internal(second)
    self.assertEqual([u['name'] for u in server.get_auth_users_internal()], ['Changed A','Changed B'])

  def test_same_field_conflict_is_rejected(self):
    first, second = server.get_auth_users_internal(), server.get_auth_users_internal()
    first[0]['name']='First'
    second[0]['name']='Second'
    server.save_auth_users_internal(first)
    with self.assertRaises(HTTPException) as error: server.save_auth_users_internal(second)
    self.assertEqual(error.exception.status_code,409)
    self.assertEqual(server.get_auth_users_internal()[0]['name'],'First')

  def test_parallel_atomic_updates_keep_every_increment(self):
    def increment(_):
      server.atomic_update_state('counter', lambda data: {'value':data.get('value',0)+1})
    with ThreadPoolExecutor(max_workers=4) as executor: list(executor.map(increment,range(24)))
    self.assertEqual(server.load_state_payload('counter')['value'],24)

  def test_supabase_compare_and_swap_retries_a_competing_write(self):
    stored={'payload':{'count':0},'updated_at':'2026-09-14T00:00:00+00:00'}
    patches=[]
    def remote(method,path,body=None,**kwargs):
      if method=='POST': return None
      if method=='GET': return [deepcopy(stored)]
      if method=='PATCH':
        patches.append(path)
        if len(patches)==1:
          stored.update(payload={'count':10},updated_at='2026-09-14T00:00:01+00:00')
          return []
        stored.update(deepcopy(body))
        return [deepcopy(stored)]
      self.fail(f'Unexpected request {method}')
    with patch.object(server,'using_supabase',return_value=True),patch.object(server,'supabase_request',side_effect=remote):
      result=server.atomic_update_state('counter',lambda data:{'count':data['count']+1})
    self.assertEqual(result['count'],11)
    self.assertEqual(len(patches),2)
    self.assertIn('updated_at=eq.',patches[1])
    self.assertNotEqual(patches[0],patches[1])

  def test_concurrent_same_email_registration_is_rejected(self):
    first,second=server.get_auth_users_internal(),server.get_auth_users_internal()
    first.append({'id':'c','email':'new@example.test','name':'New'})
    second.append({'id':'d','email':'new@example.test','name':'Other'})
    server.save_auth_users_internal(first)
    with self.assertRaises(HTTPException): server.save_auth_users_internal(second)
    self.assertEqual(len(server.get_auth_users_internal()),3)

  def test_forged_forwarded_header_does_not_reset_limit(self):
    def request(ip): return Request({'type':'http','headers':[(b'x-forwarded-for',ip.encode())],'client':('127.0.0.1',1234)})
    for _ in range(3): server.check_rate_limit(request('192.0.2.1'),'security-test',3,60,'a')
    server.RATE_LIMIT_STATE.clear()  # Simulate a worker with no in-memory history.
    with self.assertRaises(HTTPException) as error: server.check_rate_limit(request('192.0.2.2'),'security-test',3,60,'a')
    self.assertEqual(error.exception.status_code,429)

  def test_account_limit_survives_actual_ip_change(self):
    for index in range(3):
      request=Request({'type':'http','headers':[],'client':(f'192.0.2.{index}',1234)})
      server.check_rate_limit(request,'security-test',2,60,'a') if index < 2 else None
    with self.assertRaises(HTTPException): server.check_rate_limit(request,'security-test',2,60,'a')

  def test_export_and_delete_are_scoped_and_revoke_session(self):
    response=self.client.post('/api/auth/login',json={'email':'a@example.test','password':'TestPassword1'})
    self.assertEqual(response.status_code,200,response.text)
    headers={'Authorization':f"Bearer {response.json()['token']}"}
    exported=self.client.get('/api/auth/me/export',headers=headers)
    self.assertEqual(exported.json()['profile']['id'],'a')
    self.assertNotIn('passwordHash',exported.json()['profile'])
    self.assertEqual(exported.headers['cache-control'],'no-store')
    self.assertEqual(self.client.post('/api/auth/me/delete',headers=headers,json={'password':'wrong'}).status_code,403)
    deleted=self.client.post('/api/auth/me/delete',headers=headers,json={'password':'TestPassword1'})
    self.assertEqual(deleted.status_code,200,deleted.text)
    self.assertEqual([u['id'] for u in server.get_auth_users_internal()],['b'])
    self.assertEqual(self.client.get('/api/auth/me',headers=headers).status_code,401)

  def test_readiness_fails_when_storage_is_down(self):
    with patch.object(server,'check_data_backend_ready',return_value=True),patch.object(server,'check_document_storage_ready',return_value=False):
      response=self.client.get('/health')
    self.assertEqual(response.status_code,503)
    self.assertFalse(response.json()['ok'])

  def test_explicit_supabase_never_falls_back(self):
    with patch.dict(os.environ,{'DATA_BACKEND':'supabase'}),patch.object(server,'supabase_configured',return_value=False):
      with self.assertRaises(RuntimeError): server.get_data_backend()

  def test_scripts_are_self_hosted_and_private_responses_not_cached(self):
    response=self.client.get('/vendor/lucide.min.js')
    self.assertEqual(response.status_code,200)
    self.assertIn("script-src 'self';",response.headers['content-security-policy'])
    self.assertEqual(self.client.get('/privacy').status_code,200)

  def test_enrichment_does_not_approve_historical_records_or_replace_duration(self):
    spec=importlib.util.spec_from_file_location('enrichment', server.ROOT/'scripts/enrich-catalogue.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path=Path(self.temp.name)/'catalogue.json'
    path.write_text(json.dumps([{'name':'BA in Fashion & Retailing','category':'Creative Arts & Communication','institution':'Limkokwing University Lesotho','duration':'Verified duration','source_url':'https://example.test','review_status':'needs_admin_review'}]))
    with patch.object(module,'PROGRAMMES_FILE',path),patch.object(module,'load_fee_sources',return_value={}),patch('builtins.print'):
      module.main()
    row=json.loads(path.read_text())[0]
    self.assertEqual(row['review_status'],'needs_admin_review')
    self.assertEqual(row['duration'],'Verified duration')
    self.assertIn('Fashion design',row['skill_options'])
    self.assertNotIn('News writing',row['skill_options'])

  def test_legacy_plaintext_password_is_rejected(self):
    self.assertFalse(server.verify_password('secret', {'password': 'secret'}))

  def test_students_do_not_receive_review_state(self):
    response = self.client.post('/api/auth/login', json={'email': 'a@example.test', 'password': 'TestPassword1'})
    headers = {'Authorization': f"Bearer {response.json()['token']}"}
    with patch.object(server, 'list_state_payloads', return_value=[{'state_key': 'review_state', 'payload': {'secret': 'yes'}, 'updated_at': 'now'}]):
      data = self.client.get('/api/db/state', headers=headers).json()
    self.assertTrue(data['ok'])
    self.assertNotIn('review_state', data.get('state', {}))

  def test_admin_can_read_review_state(self):
    salt, digest = server.hash_password('TestPassword1')
    users = server.get_auth_users_internal()
    users.append({'id': 'admin', 'email': 'admin@example.test', 'name': 'Admin', 'role': 'admin', 'status': 'active', 'passwordSalt': salt, 'passwordHash': digest})
    server.save_auth_users_internal(users)
    token = self.client.post('/api/auth/login', json={'email': 'admin@example.test', 'password': 'TestPassword1'}).json()['token']
    with patch.object(server, 'list_state_payloads', return_value=[{'state_key': 'review_state', 'payload': {'secret': 'yes'}, 'updated_at': 'now'}]):
      data = self.client.get('/api/db/state', headers={'Authorization': f'Bearer {token}'}).json()
    self.assertEqual(data['state']['review_state']['secret'], 'yes')

  def test_students_cannot_download_staff_catalogue(self):
    response = self.client.post('/api/auth/login', json={'email': 'a@example.test', 'password': 'TestPassword1'})
    headers = {'Authorization': f"Bearer {response.json()['token']}"}
    self.assertEqual(self.client.get('/api/admin/catalogue', headers=headers).status_code, 403)

  def test_staff_catalogue_exposes_allowlisted_prospectus_evidence_without_local_paths(self):
    record = server.staff_catalogue_record({
      'id': 'siac-candidate',
      'institution': 'SIAC',
      'name': 'Diploma in Tourism',
      'source_path': 'C:/staff/supplied/siac-prospectus-2025-2026.pdf',
      'supportingFeeSourcePath': 'data/references/siac-prospectus-2025-2026.pdf',
      'fee_note': 'Confirm the current fee before payment.',
      'application_documents': ['Results slip'],
    })
    self.assertEqual(record['sourceUrl'], '/source-documents/siac-prospectus-2025-2026.pdf')
    self.assertEqual(record['supportingFeeSourcePath'], '/source-documents/siac-prospectus-2025-2026.pdf')
    self.assertEqual(record['sourceFile'], 'siac-prospectus-2025-2026.pdf')
    self.assertEqual(record['feeNote'], 'Confirm the current fee before payment.')
    self.assertEqual(record['applicationDocuments'], ['Results slip'])
    self.assertNotIn('C:/staff', json.dumps(record))

  def test_ai_guidance_can_cite_an_approved_allowlisted_prospectus(self):
    server._catalogue_programmes_cache = [{
      'id': 'siac-candidate',
      'institution': 'SIAC',
      'name': 'Diploma in Tourism',
      'review_status': 'approved',
      'requirements_summary': 'English D or better.',
      'source_file': 'siac-prospectus-2025-2026.pdf',
    }]
    try:
      payload = server.GuidanceRequest(matches=[{'id': 'siac-candidate', 'match': {'tier': 'qualified'}}])
      bound = server.bind_guidance_payload_to_catalogue(payload)
      self.assertEqual(bound.matches[0]['sourceUrl'], '/source-documents/siac-prospectus-2025-2026.pdf')
      self.assertEqual(bound.matches[0]['source'], '/source-documents/siac-prospectus-2025-2026.pdf')
      self.assertEqual(bound.matches[0]['sourceReview']['status'], 'unreviewed')
    finally:
      server._catalogue_programmes_cache = None

  def test_ai_guidance_rebuilds_catalogue_facts_instead_of_trusting_browser_fields(self):
    record = {
      'id': 'real-course', 'name': 'Diploma in Media', 'institution': 'Example College',
      'review_status': 'approved', 'requirements_summary': 'English D or better.',
      'source_url': 'https://college.example/prospectus', 'source_type': 'official_prospectus',
      'application_url': 'https://college.example/apply', 'application_documents': ['Results slip'],
      'fee_note': 'Confirm the current fee with the college.', 'career_options': ['Producer'],
      'skill_options': ['Editing'], 'faculty': 'Media', 'level': 'Diploma', 'duration': '3 years',
    }
    forged = {
      'id': 'real-course', 'title': 'Guaranteed Admission', 'institution': 'Fake College',
      'requirements': ['No grades required'], 'source': 'https://fake.example/offer',
      'source_type': 'forged', 'careers': ['Surgeon'], 'skills': ['Surgery'],
      'faculty': 'Medicine', 'level': 'Degree', 'duration': '1 month',
      'application': {'link': {'url': 'https://fake.example/pay'}, 'feeSummary': {'lines': ['Free tuition']}},
      'application_documents': ['No documents'], 'applicationDocuments': ['No documents'],
      'scores': {'tier': 'qualified'}, 'match': {'tier': 'almost', 'tierLabel': 'Qualified'},
    }
    with patch.object(server, '_catalogue_programmes_cache', [record]):
      bound = server.bind_guidance_payload_to_catalogue(server.GuidanceRequest(matches=[forged])).matches[0]
    compact = server.compact_match(bound)
    self.assertEqual((bound['title'], bound['institution'], bound['duration']), ('Diploma in Media', 'Example College', '3 years'))
    self.assertEqual(bound['requirements'], ['English D or better.'])
    self.assertEqual(bound['careers'], ['Producer'])
    self.assertEqual(bound['skills'], ['Editing'])
    self.assertEqual(bound['sourceType'], 'official_prospectus')
    self.assertEqual(bound['applicationDocuments'], ['Results slip'])
    self.assertEqual(bound['application']['link']['url'], 'https://college.example/apply')
    self.assertEqual(bound['application']['feeSummary']['lines'], ['Confirm the current fee with the college.'])
    self.assertEqual(compact['tier'], 'almost')
    self.assertEqual(compact['tier_label'], 'Almost')
    self.assertEqual(compact['evidence'][:2], ['Captured requirements: English D or better.', 'Source: https://college.example/prospectus'])
    self.assertNotIn('fake.example', json.dumps(server.build_request_payload(server.GuidanceRequest(matches=[bound]))))

  def test_explore_tier_and_missing_catalogue_evidence_cannot_be_promoted_by_labels_or_ai_text(self):
    record = {'id': 'thin', 'name': 'Thin Diploma', 'institution': 'Example College', 'review_status': 'approved'}
    forged = {
      'id': 'thin', 'requirements': ['Everyone qualifies'], 'source': 'https://fake.example/source',
      'application': {'link': {'url': 'https://fake.example/apply'}},
      'match': {'tier': 'qualified', 'tierLabel': 'Qualified'},
    }
    with patch.object(server, '_catalogue_programmes_cache', [record]):
      bound = server.bind_guidance_payload_to_catalogue(server.GuidanceRequest(matches=[forged], question='Can I apply?'))
    compact = server.compact_match(bound.matches[0])
    self.assertEqual(compact['tier'], 'explore')
    self.assertEqual(compact['tier_label'], 'Explore')
    self.assertEqual(compact['requirements'], [])
    self.assertIsNone(compact['source'])
    self.assertIsNone(compact['application']['link'])
    self.assertFalse(server.is_recommendable_match(compact))
    self.assertFalse(server.is_recommendable_match({'tier': 'explore', 'tier_label': 'Qualified'}))
    guidance = server.normalize_ai_guidance({
      'summary': 'You qualify for Thin Diploma.', 'direct_answer': 'Apply now.',
      'top_recommendations': [{'programme': 'Thin Diploma', 'institution': 'Example College'}],
      'study_plan': ['Pay the fee now.'],
    }, bound)
    self.assertEqual(guidance['top_recommendations'], [])
    self.assertIn('No qualified or almost-qualified recommendation', guidance['summary'])
    self.assertIn('cannot recommend an application-ready course', guidance['direct_answer'])
    self.assertNotIn('Thin Diploma', guidance['direct_answer'])
    self.assertNotIn('Pay the fee now.', guidance['study_plan'])

  def test_ai_guidance_hard_gate_failure_overrides_favourable_tier(self):
    record = {'id': 'math-course', 'name': 'Math Course', 'institution': 'Example College',
              'review_status': 'approved', 'requirements_summary': 'Mathematics C or better.'}
    with patch.object(server, '_catalogue_programmes_cache', [record]):
      payload = server.bind_guidance_payload_to_catalogue(server.GuidanceRequest(matches=[{
        'id': 'math-course', 'hard_gate_passed': False,
        'match': {'tier': 'qualified', 'tierLabel': 'Qualified', 'hardGatePassed': True},
      }]))
    self.assertEqual(payload.matches, [])
    compact = server.compact_match(payload.blockedMatches[0])
    self.assertEqual(compact['tier'], 'blocked')
    self.assertFalse(compact['hard_gate_passed'])
    self.assertFalse(server.is_recommendable_match(compact))

  def test_no_eligible_matches_get_relevant_follow_up_questions(self):
    payload = server.GuidanceRequest(
      question='What blocks me?',
      matches=[{'title': 'Explore Course', 'institution': 'Example College', 'match': {'tier': 'explore'}}],
      blockedMatches=[{'title': 'Blocked Course', 'institution': 'Example College',
                       'match': {'tier': 'blocked', 'requirementGaps': ['Mathematics C or better.']}}],
    )
    fallback = server.build_fallback(payload)
    self.assertTrue(any('blocks your closest pathway' in item for item in fallback['next_questions']))
    self.assertFalse(any('qualified or almost-qualified matches' in item for item in fallback['next_questions']))
    guidance = server.normalize_ai_guidance({
      'summary': 'You qualify.',
      'next_questions': ['Which qualified option will you apply to?'],
    }, payload)
    self.assertEqual(guidance['next_questions'], fallback['next_questions'])
    self.assertIn('Main blocker: Mathematics C or better.', guidance['direct_answer'])
    self.assertNotIn('better..', guidance['direct_answer'])
    self.assertEqual(guidance['blockers'], ['Blocked Course at Example College: Mathematics C or better.'])

  def test_fallback_does_not_expose_provider_error_details(self):
    guidance = server.build_fallback(server.GuidanceRequest(), 'provider-secret-and-request-details')
    self.assertNotIn('provider-secret-and-request-details', guidance['summary'])
    self.assertIn('local matcher guidance', guidance['summary'])

  def test_sesotho_language_is_allowlisted_and_preserves_blocker_evidence(self):
    payload = server.validate_and_sanitize_guidance_payload(server.GuidanceRequest(
      language='st', question='What blocks me?', blockedMatches=[{
        'title': 'Blocked Course', 'institution': 'Example College',
        'match': {'tier': 'blocked'}, 'requirementGaps': ['Mathematics C or better'],
      }],
    ))
    self.assertEqual(server.build_request_payload(payload)['task']['language'], 'st')
    guidance = server.normalize_ai_guidance({'summary': 'You qualify.', 'direct_answer': 'Apply now.'}, payload)
    self.assertIn('Mathematics C or better', guidance['direct_answer'])
    self.assertNotIn('Apply now.', guidance['direct_answer'])
    self.assertEqual(guidance['top_recommendations'], [])
    self.assertEqual(server.validate_and_sanitize_guidance_payload(server.GuidanceRequest(language='fr')).language, 'en')

  def test_sesotho_local_fallback_keeps_provider_errors_private(self):
    guidance = server.build_fallback(server.GuidanceRequest(language='st'), 'private-provider-token')
    self.assertIn('Hajoale', guidance['summary'])
    self.assertNotIn('private-provider-token', json.dumps(guidance))
    self.assertEqual(guidance['top_recommendations'], [])

  def test_fresh_greeting_is_short_and_saved_without_fake_matches(self):
    login = self.client.post('/api/auth/login', json={'email': 'a@example.test', 'password': 'TestPassword1'})
    headers = {'Authorization': f"Bearer {login.json()['token']}"}
    with patch.object(server, 'call_gemini', side_effect=AssertionError('A greeting should not need a model call')):
      response = self.client.post('/api/ai/guidance', headers=headers, json={
        'question': 'hey', 'language': 'en',
        'conversation': [{'id': 'first-hello', 'role': 'user', 'content': 'hey'}],
        'matches': [{'id': 'untrusted-course', 'match': {'tier': 'qualified'}}],
      })
    self.assertEqual(response.status_code, 200, response.text)
    data = response.json()
    self.assertEqual(data['mode'], 'local_conversation')
    self.assertIn('Hello!', data['guidance']['direct_answer'])
    self.assertEqual(data['guidance']['top_recommendations'], [])
    self.assertNotIn('blocked', data['guidance']['direct_answer'].lower())
    history = self.client.get('/api/ai/chat', headers=headers).json()['messages']
    self.assertEqual([item['role'] for item in history[-2:]], ['user', 'assistant'])
    self.assertEqual(history[-1]['content'], data['guidance']['direct_answer'])

  def test_fresh_course_question_asks_for_grades_without_requiring_interests(self):
    login = self.client.post('/api/auth/login', json={'email': 'a@example.test', 'password': 'TestPassword1'})
    headers = {'Authorization': f"Bearer {login.json()['token']}"}
    response = self.client.post('/api/ai/guidance', headers=headers, json={
      'question': 'What can I study?', 'matches': [{'id': 'untrusted-course', 'match': {'tier': 'qualified'}}],
    })
    self.assertEqual(response.status_code, 200, response.text)
    answer = response.json()['guidance']['direct_answer']
    self.assertIn('subject grades', answer)
    self.assertIn('do not have to choose interests', answer)
    self.assertNotIn('blocked', answer.lower())

  def test_ai_match_grade_evidence_overrides_forged_qualification(self):
    record = {
      'id': 'six-subjects', 'name': 'Six Subject Diploma', 'institution': 'Example College',
      'review_status': 'approved',
      'requirements_summary': 'At least 4 subjects with a grade of C or better and 2 subjects with a grade of D or better.',
    }
    login = self.client.post('/api/auth/login', json={'email': 'a@example.test', 'password': 'TestPassword1'})
    headers = {'Authorization': f"Bearer {login.json()['token']}"}
    grades = [{'code': code, 'grade': 'C'} for code in ('MATH', 'ENG', 'SES', 'BIO', 'PSCI')]
    response_data = {'mode': 'gemini', 'model': 'test', 'guidance': {'direct_answer': 'You qualify. Apply now.'}}
    with patch.object(server, '_catalogue_programmes_cache', [record]), patch.object(server, 'call_gemini', return_value=response_data) as call_ai:
      response = self.client.post('/api/ai/guidance', headers=headers, json={
        'question': 'Can I study this course?', 'profile': {'grades': grades},
        'matches': [{'id': 'six-subjects', 'match': {
          'tier': 'qualified', 'reasons': ['Guaranteed admission'],
          'requirementGaps': ['Pay us now'],
        }}],
      })
    self.assertEqual(response.status_code, 200, response.text)
    sent = call_ai.call_args.args[1]
    self.assertEqual(sent['recommendable_matches'], [])
    self.assertEqual(sent['explore_matches'][0]['tier'], 'explore')
    self.assertIn('At least 6 subjects at D or better', sent['explore_matches'][0]['requirement_gaps'][0])
    self.assertNotIn('Guaranteed admission', json.dumps(sent))
    self.assertNotIn('Pay us now', json.dumps(sent))
    self.assertNotIn('You qualify', response.json()['guidance']['direct_answer'])

  def test_ai_match_grade_evidence_preserves_supported_tier(self):
    summary = 'At least 4 subjects with a grade of C or better and 2 subjects with a grade of D or better.'
    grades = {code: 'C' for code in ('MATH', 'ENG', 'SES', 'BIO', 'PSCI', 'ACC')}
    payload = server.GuidanceRequest(profile={'grades': grades}, matches=[{
      'id': 'real', 'requirementsSummary': summary, 'tier': 'qualified',
      'match': {'tier': 'qualified', 'reasons': ['Guaranteed admission']},
    }])
    verified = server.verify_guidance_grade_evidence(payload)
    self.assertEqual(verified.matches[0]['tier'], 'qualified')
    self.assertEqual(verified.matches[0]['match']['reasons'], [])
    self.assertEqual(server.captured_grade_gaps(summary, grades), [])
    self.assertTrue(any('English: grade not entered' in gap for gap in server.captured_grade_gaps('Five passes including English and Mathematics.', {'MATH': 'C', 'BIO': 'C'})))

  def test_captured_subject_rules_require_the_grades_named_by_the_source(self):
    summary = 'COSC/LGCSE with credit in Mathematics and Physical Science, and pass in English Language.'
    grades = {'MATH': 'C', 'ENG': 'D', 'BIO': 'C'}
    gaps, checked = server.captured_grade_check(summary, grades)
    self.assertTrue(checked)
    self.assertTrue(any('Physical Science or Physics' in gap and 'C or better' in gap for gap in gaps))
    self.assertEqual(server.captured_grade_gaps(summary, {**grades, 'PSCI': 'C'}), [])
    nul = 'Sat for a minimum of six (6) subjects. Obtained a B grade or better in Mathematics.'
    self.assertTrue(any('Mathematics: entered C; B or better' in gap for gap in server.captured_grade_gaps(nul, {**grades, 'PSCI': 'C', 'SES': 'C', 'ACC': 'C'})))
    self.assertIn('At least 6 subjects required', server.captured_grade_gaps(nul, grades)[-1])

  def test_captured_alternative_subjects_and_nursing_grades(self):
    accounting = 'LGCSE/COSC with minimum 6 subjects, 4 credits including Mathematics or English or Accounting.'
    grades = {code: 'C' for code in ('MATH', 'SES', 'BIO', 'PSCI', 'AGR', 'CSK')}
    self.assertEqual(server.captured_grade_gaps(accounting, grades), [])
    without_options = {code: 'C' for code in ('SES', 'BIO', 'PSCI', 'AGR', 'CSK', 'FNU')}
    self.assertTrue(any('Mathematics, English, or Accounting' in gap for gap in server.captured_grade_gaps(accounting, without_options)))
    nursing = ('Minimum of six subjects, including D or better in Mathematics, D or better in English Language, '
               'C or better in Physics/Chemistry, C or better in Biology, and C or better in any other two subjects.')
    with_weak_biology = {'MATH': 'C', 'ENG': 'C', 'PSCI': 'C', 'BIO': 'D', 'SES': 'C', 'ACC': 'C'}
    self.assertTrue(any('Biology: entered D; C or better' in gap for gap in server.captured_grade_gaps(nursing, with_weak_biology)))
    self.assertEqual(server.captured_grade_gaps(nursing, {**with_weak_biology, 'BIO': 'C'}), [])
    self.assertFalse(server.captured_grade_check(nursing, {**with_weak_biology, 'BIO': 'C'})[1])
    self.assertFalse(server.captured_grade_check(accounting + ' Aggregate not exceeding 36.', grades)[1])
    ambiguous = 'IGCSE with 5 Passes including Credit in English, Mathematics/Statistics and Science (Biology or Chemistry).'
    self.assertFalse(server.captured_grade_check(ambiguous, {**grades, 'ENG': 'C'})[1])

  def test_ai_does_not_upgrade_unparsed_catalogue_prose(self):
    record = {
      'id': 'unparsed', 'name': 'Commercial Diploma', 'institution': 'Example College',
      'review_status': 'approved',
      'requirements_summary': 'Commercial diploma pathway; prospectus lists commerce-related subject requirements.',
    }
    login = self.client.post('/api/auth/login', json={'email': 'a@example.test', 'password': 'TestPassword1'})
    headers = {'Authorization': f"Bearer {login.json()['token']}"}
    result = {'mode': 'gemini', 'model': 'test', 'guidance': {'direct_answer': 'You qualify. Apply now.'}}
    with patch.object(server, '_catalogue_programmes_cache', [record]), patch.object(server, 'call_gemini', return_value=result) as call_ai:
      response = self.client.post('/api/ai/guidance', headers=headers, json={
        'question': 'Can I apply?', 'profile': {'grades': [{'code': 'MATH', 'grade': 'C'}]},
        'matches': [{'id': 'unparsed', 'match': {'tier': 'qualified'}}],
      })
    self.assertEqual(response.status_code, 200, response.text)
    self.assertEqual(call_ai.call_args.args[1]['recommendable_matches'], [])
    self.assertEqual(call_ai.call_args.args[1]['explore_matches'][0]['tier'], 'explore')
    self.assertNotIn('You qualify', response.json()['guidance']['direct_answer'])

  def test_guidance_grade_map_accepts_known_subject_labels(self):
    self.assertEqual(server.guidance_grade_map({'grades': [
      {'subject': 'English Language', 'grade': 'D'}, {'subject': 'Mathematics', 'grade': 'C'},
      {'subject': 'Invented subject', 'grade': 'A'},
    ]}), {'ENG': 'D', 'MATH': 'C'})

  def test_follow_up_topics_ask_for_one_relevant_answer(self):
    self.assertEqual(server.guidance_question_type('What should I focus on studying next based on my confirmed grades?'), 'study_plan')
    self.assertEqual(server.guidance_question_type('What information do you still need from me before recommending courses?'), 'missing')
    self.assertEqual(server.guidance_question_type('Summarize my current programme guidance in two short sentences.'), 'summary')
    self.assertIn('only one key: direct_answer', server.DEVELOPER_PROMPT)
    no_grades = server.GuidanceRequest(question='What confirmed grade or entry requirement blocks my current options?')
    answer = server.conversational_guidance(no_grades)['direct_answer']
    self.assertIn('Missing grades do not mean you are blocked', answer)
    self.assertEqual(server.guidance_question_type('How do I apply?'), 'other')
    self.assertIsNone(server.conversational_guidance(server.GuidanceRequest(question='How do I apply?')))

  def test_general_question_without_grades_can_use_the_model(self):
    login = self.client.post('/api/auth/login', json={'email': 'a@example.test', 'password': 'TestPassword1'})
    headers = {'Authorization': f"Bearer {login.json()['token']}"}
    result = {'mode': 'gemini', 'model': 'test', 'guidance': {'direct_answer': 'EduGuide helps you explore school programmes.'}}
    with patch.object(server, 'call_gemini', return_value=result) as call_ai:
      response = self.client.post('/api/ai/guidance', headers=headers, json={'question': 'How does EduGuide work?'})
    self.assertEqual(response.status_code, 200, response.text)
    self.assertTrue(call_ai.called)
    self.assertEqual(response.json()['guidance']['direct_answer'], 'EduGuide helps you explore school programmes.')

  def test_profile_interests_are_saved_per_account(self):
    login = self.client.post('/api/auth/login', json={'email': 'a@example.test', 'password': 'TestPassword1'})
    headers = {'Authorization': f"Bearer {login.json()['token']}"}
    response = self.client.put('/api/auth/me', headers=headers, json={
      'name': 'a', 'district': '', 'stream': '', 'leavingYear': '',
      'interests': ['Technology & IT'], 'grades': {},
    })
    self.assertEqual(response.status_code, 200, response.text)
    self.assertEqual(self.client.get('/api/auth/me', headers=headers).json()['user']['interests'], ['Technology & IT'])
    self.assertEqual(next(user for user in server.get_auth_users_internal() if user['id'] == 'b')['interests'], [])

  def test_invalid_gemini_response_is_labelled_local_fallback(self):
    client = Mock()
    with patch.object(server, 'get_gemini_api_key', return_value='test-key'), \
         patch('google.genai.Client', return_value=client):
      for invalid_response in ('not JSON', '[]'):
        client.models.generate_content.return_value.text = invalid_response
        result = server.call_gemini(server.GuidanceRequest(), {})
        self.assertEqual(result['mode'], 'local_fallback')
        self.assertEqual(result['provider'], 'gemini')
    self.assertTrue(client.models.generate_content.called)

  def test_invalid_openai_response_is_labelled_local_fallback(self):
    client = Mock()
    with patch.object(server, 'get_openai_api_key', return_value='test-key'), \
         patch.object(server, 'OpenAI', return_value=client):
      for invalid_response in ('not JSON', '[]'):
        client.responses.create.return_value.output_text = invalid_response
        result = server.call_openai(server.GuidanceRequest(), {})
        self.assertEqual(result['mode'], 'local_fallback')
        self.assertEqual(result['provider'], 'openai')
    self.assertTrue(client.responses.create.called)

  def test_ai_guidance_endpoint_rejects_forged_catalogue_evidence(self):
    record = {'id': 'real-course', 'name': 'Real Course', 'institution': 'Example College',
              'review_status': 'approved', 'requirements_summary': 'English D or better.',
              'source_url': 'https://college.example/prospectus'}
    login = self.client.post('/api/auth/login', json={'email': 'a@example.test', 'password': 'TestPassword1'})
    self.assertEqual(login.status_code, 200)
    headers = {'Authorization': f"Bearer {login.json()['token']}"}
    fake_result = {'mode': 'gemini', 'model': 'test', 'guidance': {
      'summary': 'You qualify.', 'direct_answer': 'Apply now.',
      'top_recommendations': [{'programme': 'Real Course', 'institution': 'Example College'}],
    }}
    with patch.object(server, '_catalogue_programmes_cache', [record]), patch.object(server, 'call_gemini', return_value=fake_result) as call_ai:
      response = self.client.post('/api/ai/guidance', headers=headers, json={'profile': {'grades': [{'subject': 'English', 'grade': 'D'}]}, 'matches': [{
        'id': 'real-course', 'requirements': ['No grades required'],
        'source': 'https://fake.example/prospectus',
        'match': {'tier': 'qualified', 'tierLabel': 'Qualified'},
      }]})
    self.assertEqual(response.status_code, 200)
    sent_match = call_ai.call_args.args[1]['recommendable_matches'][0]
    self.assertEqual(sent_match['requirements'], ['English D or better.'])
    self.assertEqual(sent_match['source'], 'https://college.example/prospectus')
    self.assertNotIn('fake.example', json.dumps(sent_match))
    recommendation = response.json()['guidance']['top_recommendations'][0]
    self.assertIn('English D or better.', recommendation['evidence'])
    self.assertEqual(recommendation['evidence_source'], 'https://college.example/prospectus')

  def test_ai_guidance_endpoint_passes_sesotho_preference_to_provider(self):
    record = {'id': 'real-course', 'name': 'Real Course', 'institution': 'Example College',
              'review_status': 'approved', 'requirements_summary': 'English D or better.'}
    login = self.client.post('/api/auth/login', json={'email': 'a@example.test', 'password': 'TestPassword1'})
    headers = {'Authorization': f"Bearer {login.json()['token']}"}
    result = {'mode': 'gemini', 'model': 'test', 'guidance': {'summary': 'Tataiso ea hao.'}}
    with patch.object(server, '_catalogue_programmes_cache', [record]), patch.object(server, 'call_gemini', return_value=result) as call_ai:
      response = self.client.post('/api/ai/guidance', headers=headers, json={
        'language': 'st', 'profile': {'grades': [{'subject': 'English', 'grade': 'D'}]},
        'matches': [{'id': 'real-course', 'match': {'tier': 'qualified'}}],
      })
    self.assertEqual(response.status_code, 200, response.text)
    self.assertEqual(response.json()['language'], 'st')
    self.assertEqual(call_ai.call_args.args[1]['task']['language'], 'st')

  def test_supabase_chat_write_failure_preserves_existing_history(self):
    methods = []
    def remote(method, path, body=None, **kwargs):
      methods.append(method)
      if method == 'POST': raise RuntimeError('storage unavailable')
      self.fail(f'Unexpected request {method} {path}')
    message = {'id': 'new-message', 'role': 'user', 'content': 'Hello', 'at': '2026-09-14T00:00:00Z'}
    with patch.object(server, 'using_supabase', return_value=True), patch.object(server, 'supabase_request', side_effect=remote):
      saved, synced = server.safe_save_ai_chat_history('a', [message])
    self.assertFalse(synced)
    self.assertEqual(saved[0]['content'], 'Hello')
    self.assertEqual(methods, ['POST'])

  def test_supabase_chat_writes_before_pruning_old_messages(self):
    calls = []
    def remote(method, path, body=None, **kwargs):
      calls.append((method, path, kwargs))
      if method == 'GET':
        return [
          {'id': 'new-message', 'role': 'assistant', 'content': 'Hello', 'created_at': '2026-09-14T00:00:01Z'},
          {'id': 'old-message', 'role': 'user', 'content': 'Question', 'created_at': '2026-09-14T00:00:00Z'},
        ]
      return None
    message = {'id': 'new-message', 'role': 'assistant', 'content': 'Hello', 'at': '2026-09-14T00:00:01Z'}
    with patch.object(server, 'using_supabase', return_value=True), patch.object(server, 'supabase_request', side_effect=remote):
      server.save_ai_chat_history('a', [message])
    self.assertEqual([method for method, _, _ in calls], ['POST', 'GET', 'DELETE'])
    self.assertIn('on_conflict=id', calls[0][1])
    self.assertIn('resolution=ignore-duplicates', calls[0][2]['prefer'])
    self.assertIn('created_at=lt.', calls[2][1])

  def test_chat_history_and_clear_return_error_when_storage_fails(self):
    login = self.client.post('/api/auth/login', json={'email': 'a@example.test', 'password': 'TestPassword1'})
    headers = {'Authorization': f"Bearer {login.json()['token']}"}
    with patch.object(server, 'list_ai_chat_history', side_effect=RuntimeError('storage unavailable')):
      response = self.client.get('/api/ai/chat', headers=headers)
    self.assertEqual(response.status_code, 503)
    with patch.object(server, 'clear_ai_chat_history', side_effect=RuntimeError('storage unavailable')):
      response = self.client.delete('/api/ai/chat', headers=headers)
    self.assertEqual(response.status_code, 503)

  def test_ai_guidance_reports_unsynced_chat_after_save_failure(self):
    record = {'id': 'real-course', 'name': 'Real Course', 'institution': 'Example College',
              'review_status': 'approved', 'requirements_summary': 'English D or better.',
              'source_url': 'https://college.example/prospectus'}
    login = self.client.post('/api/auth/login', json={'email': 'a@example.test', 'password': 'TestPassword1'})
    headers = {'Authorization': f"Bearer {login.json()['token']}"}
    fake_result = {'mode': 'gemini', 'model': 'test', 'guidance': {'summary': 'Review the requirements.'}}
    with patch.object(server, '_catalogue_programmes_cache', [record]), \
         patch.object(server, 'call_gemini', return_value=fake_result), \
         patch.object(server, 'save_ai_chat_history', side_effect=RuntimeError('storage unavailable')):
      response = self.client.post('/api/ai/guidance', headers=headers, json={'matches': [{'id': 'real-course'}]})
    self.assertEqual(response.status_code, 200, response.text)
    self.assertFalse(response.json()['chatSynced'])
    self.assertEqual(response.json()['chat'][-1]['role'], 'assistant')

  def test_ai_guidance_cannot_upgrade_unapproved_or_unevidenced_matches(self):
    server._catalogue_programmes_cache = [
      {'id': 'open', 'name': 'Open Degree', 'institution': 'NUL', 'review_status': 'approved', 'requirements_summary': 'English C'},
      {'id': 'thin', 'name': 'Thin Diploma', 'institution': 'NUL', 'review_status': 'approved', 'requirements_summary': ''},
      {'id': 'hidden', 'name': 'Hidden', 'institution': 'Imperial', 'review_status': 'needs_admin_review', 'requirements_summary': 'Anything'},
    ]
    payload = server.GuidanceRequest(matches=[
      {'id': 'hidden', 'title': 'Forged', 'institution': 'NUL', 'match': {'tier': 'qualified'}},
      {'id': 'thin', 'title': 'Forged thin', 'institution': 'NUL', 'match': {'tier': 'qualified'}},
      {'id': 'open', 'title': 'Forged name', 'institution': 'Wrong', 'match': {'tier': 'qualified'}},
    ])
    bound = server.bind_guidance_payload_to_catalogue(payload)
    self.assertEqual([item['id'] for item in bound.matches], ['thin', 'open'])
    self.assertEqual(bound.matches[0]['match']['tier'], 'explore')
    self.assertEqual(bound.matches[1]['title'], 'Open Degree')
    self.assertEqual(bound.matches[1]['institution'], 'NUL')
    server._catalogue_programmes_cache = None

  def test_ai_guidance_uses_the_latest_admin_source_review(self):
    server._catalogue_programmes_cache = [
      {
        'id': 'open',
        'name': 'Open Degree',
        'institution': 'NUL',
        'review_status': 'approved',
        'requirements_summary': 'English C',
        'source_url': 'https://old.example/programmes',
      }
    ]
    review_state = {
      'programmeStatuses': {'open': 'approved'},
      'programmeEdits': {
        'open': {
          'reviewStatus': 'approved',
          'reviewedAt': server.now_iso(),
          'sourceUrl': 'https://current.example/programmes',
        }
      },
    }
    payload = server.GuidanceRequest(matches=[{'id': 'open', 'match': {'tier': 'qualified'}}])
    try:
      with patch.object(server, 'load_state_payload', return_value=review_state):
        bound = server.bind_guidance_payload_to_catalogue(payload)
      self.assertEqual(bound.matches[0]['sourceUrl'], 'https://current.example/programmes')
      self.assertEqual(bound.matches[0]['sourceReview']['status'], 'current')
      compact = server.compact_match(bound.matches[0])
      self.assertIn('Source review: Source checked recently', compact['evidence'])
    finally:
      server._catalogue_programmes_cache = None

  def test_ai_guidance_respects_a_later_admin_flag(self):
    server._catalogue_programmes_cache = [
      {
        'id': 'flagged',
        'name': 'Flagged Degree',
        'institution': 'NUL',
        'review_status': 'approved',
        'requirements_summary': 'English C',
      }
    ]
    payload = server.GuidanceRequest(matches=[{'id': 'flagged', 'match': {'tier': 'qualified'}}])
    try:
      with patch.object(server, 'load_state_payload', return_value={'programmeStatuses': {'flagged': 'flagged'}}):
        bound = server.bind_guidance_payload_to_catalogue(payload)
      self.assertEqual(bound.matches, [])
    finally:
      server._catalogue_programmes_cache = None

  def test_public_catalogue_runtime_applies_safe_live_edits_without_private_review_data(self):
    server._catalogue_programmes_cache = [
      {
        'id': 'open',
        'institution': 'NUL',
        'name': 'Open Degree',
        'review_status': 'approved',
        'requirements_summary': 'English C',
        'source_url': 'https://old.example/programmes',
        'source_path': 'data/private-source.pdf',
        'source_note': 'Internal review note',
      },
      {
        'id': 'flagged',
        'institution': 'NUL',
        'name': 'Flagged Degree',
        'review_status': 'approved',
        'requirements_summary': 'English C',
      },
    ]
    review_state = {
      'programmeStatuses': {'flagged': 'flagged'},
      'programmeEdits': {
        'open': {
          'reviewStatus': 'approved',
          'requirementsSummary': 'English C or better',
          'sourceUrl': 'https://current.example/programmes',
          'reviewedAt': server.now_iso(),
          'sourcePath': 'C:/staff/private.pdf',
          'sourceNote': 'Do not expose this',
          'feeNote': 'Private draft note',
        }
      },
    }
    try:
      with patch.object(server, 'load_state_payload', return_value=review_state):
        response = self.client.get('/api/catalogue/runtime')
      self.assertEqual(response.status_code, 200, response.text)
      self.assertEqual(response.headers['cache-control'], 'no-store')
      programmes = {item['id']: item for item in response.json()['programmes']}
      self.assertEqual(programmes['open']['requirementsSummary'], 'English C or better')
      self.assertEqual(programmes['open']['sourceUrl'], 'https://current.example/programmes')
      self.assertIn('reviewedAt', programmes['open'])
      self.assertEqual(programmes['flagged'], {'id': 'flagged', 'reviewStatus': 'flagged'})
      serialized = json.dumps(programmes)
      self.assertNotIn('private.pdf', serialized)
      self.assertNotIn('Do not expose this', serialized)
      self.assertNotIn('Private draft note', serialized)
    finally:
      server._catalogue_programmes_cache = None

  def test_public_catalogue_omits_local_file_paths(self):
    catalog = (Path(__file__).resolve().parents[1] / 'data' / 'admin-catalog.js').read_text(encoding='utf-8')
    self.assertNotIn('C:/Users/', catalog)
    self.assertNotIn('C:\\Users\\', catalog)

  def test_public_runtime_can_publish_an_allowlisted_prospectus_without_leaking_its_path(self):
    server._catalogue_programmes_cache = [{
      'id': 'siac-candidate',
      'institution': "St Mary's Integrative Applied College (SIAC)",
      'name': 'Diploma in Tourism and Travel Management',
      'review_status': 'needs_admin_review',
      'requirements_summary': 'Two credits including English and Geography or History.',
      'source_file': 'siac-prospectus-2025-2026.pdf',
      'source_path': 'C:/staff/supplied/siac-prospectus-2025-2026.pdf',
    }]
    try:
      with patch.object(server, 'load_state_payload', return_value={'programmeStatuses': {'siac-candidate': 'approved'}}):
        response = self.client.get('/api/catalogue/runtime')
      self.assertEqual(response.status_code, 200, response.text)
      candidate = next(item for item in response.json()['programmes'] if item['id'] == 'siac-candidate')
      self.assertEqual(candidate['sourceUrl'], '/source-documents/siac-prospectus-2025-2026.pdf')
      self.assertEqual(candidate['reviewStatus'], 'approved')
      self.assertNotIn('sourcePath', candidate)
      self.assertNotIn('sourceFile', candidate)
      self.assertNotIn('C:/staff', json.dumps(candidate))
    finally:
      server._catalogue_programmes_cache = None

  def test_public_source_library_serves_only_allowlisted_prospectuses(self):
    for file_name in (
      'siac-prospectus-2025-2026.pdf',
      'st-elizabeth-college-subject-prospectus-supplied.pdf',
    ):
      response = self.client.get(f'/source-documents/{file_name}')
      self.assertEqual(response.status_code, 200, response.text)
      self.assertEqual(response.headers['content-type'], 'application/pdf')
      self.assertTrue(response.content.startswith(b'%PDF'))
    self.assertEqual(self.client.get('/source-documents/private-review.pdf').status_code, 404)


if __name__=='__main__': unittest.main()
