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


if __name__=='__main__': unittest.main()
