import os
import json
import importlib.util
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
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


if __name__=='__main__': unittest.main()
