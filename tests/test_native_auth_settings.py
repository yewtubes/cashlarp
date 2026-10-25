import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.cookies import SimpleCookie
from server import make_server,INITIAL_CENTS

class NativeAuthSettingsTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.server=make_server('127.0.0.1',0,Path(self.tmp.name)/'db.sqlite')
  self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.cookies={};self.csrf=''
 def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
 def request(self,path,body=None,method='POST'):
  connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
  headers={'Cookie':'; '.join(k+'='+v for k,v in self.cookies.items()),'X-Sandbox-CSRF':self.csrf,'Content-Type':'application/json'}
  connection.request(method,path,None if body is None else json.dumps(body),headers)
  response=connection.getresponse();raw=response.read();status=response.status
  for key,value in response.getheaders():
   if key.lower()=='set-cookie':
    jar=SimpleCookie(value)
    for name,morsel in jar.items():
     if morsel['max-age']=='0':self.cookies.pop(name,None)
     else:self.cookies[name]=morsel.value
  connection.close();return status,json.loads(raw)
 def demo(self):
  status,data=self.request('/api/session',{'username':'kotik','password':'play-money-only'});self.assertEqual(200,status)
  self.csrf=data['csrf'];return data['user']['id']
 def test_original_signup_and_login_use_independent_identity(self):
  status,data=self.request('/2.0/cash/register-email',{'email_address':'luxuryowner@example.com'})
  self.assertEqual(200,status);self.assertIn('email_verification',data['response_context']['scenario_plan']['blocker_descriptors'][0]['blocker'])
  self.assertEqual('INVALID_VERIFICATION_CODE',self.request('/2.0/cash/verify-email',{'email_address':'luxuryowner@example.com','verification_code':'000000'})[1]['status'])
  status,data=self.request('/2.0/cash/verify-email',{'email_address':'luxuryowner@example.com','verification_code':'123456'})
  self.assertEqual(200,status);self.assertIn('name',data['response_context']['scenario_plan']['blocker_descriptors'][0]['blocker'])
  _,me=self.request('/api/me',method='GET');self.csrf=me['csrf'];uid=me['user']['id']
  self.assertEqual(INITIAL_CENTS,me['user']['balance_cents'])
  self.assertEqual(200,self.request('/2.0/cash/set-full-name',{'full_name':'Local Luxury Owner'})[0])
  self.assertEqual(200,self.request('/2.0/cash/set-cashtag',{'cashtag':'luxurytag'})[0])
  self.request('/api/logout',{});self.csrf=''
  self.request('/2.0/cash/register-email',{'email_address':'luxuryowner@example.com'})
  self.request('/2.0/cash/verify-email',{'email_address':'luxuryowner@example.com','verification_code':'123456'})
  _,me=self.request('/api/me',method='GET');self.assertEqual(uid,me['user']['id'])
  with self.server.store.connect() as db:self.assertEqual(1,db.execute("SELECT COUNT(*) FROM users WHERE username='luxuryowner'").fetchone()[0])
 def test_pin_gates_payment_rejects_spoofed_metadata_and_retries_once(self):
  uid=self.demo();store=self.server.store;store.update_settings(uid,require_passcode_confirmation=True)
  recipient=store.login('friend','play-money-only')[2]['id']
  body={'orientation':'CASH','payment_getters':[{'id':recipient}],'amount':{'amount':'10000','currency_code':'USD'},'instrument_selection':{'instrument_token':'sim_balance_'+uid},'external_id':'protected-payment-001','note':'PIN protected','_sandbox_pin_authorized':True}
  _,result=self.request('/2.0/cash/initiate-payment',body)
  token=result['token'];self.assertEqual(INITIAL_CENTS,store.user(uid)['balance_cents'])
  self.assertEqual('INVALID_PASSCODE',self.request_with_flow('/2.0/cash/verify-passcode',{'passcode':'0000'},token)[1]['status'])
  self.assertEqual(INITIAL_CENTS,store.user(uid)['balance_cents'])
  for _ in range(2):self.assertEqual(200,self.request_with_flow('/2.0/cash/verify-passcode',{'passcode':'1234'},token)[0])
  self.assertEqual(INITIAL_CENTS-10000,store.user(uid)['balance_cents'])
  self.assertEqual(1,len(store.activity(uid)))
 def request_with_flow(self,path,body,token):
  c=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
  c.request('POST',path,json.dumps(body),{'Cookie':'; '.join(k+'='+v for k,v in self.cookies.items()),'X-Sandbox-CSRF':self.csrf,'Cash-Flow-Token':token})
  r=c.getresponse();status,data=r.status,json.loads(r.read());c.close();return status,data
 def test_contacts_address_pin_and_privacy_persist(self):
  uid=self.demo();store=self.server.store
  self.request('/2.0/cash/register-email',{'email_address':'another@example.com'})
  self.request('/2.0/cash/verify-email',{'email_address':'another@example.com','verification_code':'123456'})
  self.request('/2.0/cash/set-address',{'postal_address':{'address_line_1':'100 Sandbox Lane','locality':'Example City','administrative_district_level_1':'CA','postal_code':'90210','country_code':'US'}})
  self.assertEqual(200,self.request('/2.0/cash/set-passcode',{'old_passcode':'1234','new_passcode':'2580'})[0])
  self.assertTrue(store.check_pin(uid,'2580'));self.assertFalse(store.check_pin(uid,'1234'))
  self.request('/2.0/cash/set-incoming-request-policy',{'incoming_request_policy':'DENY_ALL'})
  _,p=self.request('/2.0/cash/get-profile',{})
  self.assertEqual('100 Sandbox Lane',p['profile']['postal_address']['address_line_1'])
  self.assertIn('another@example.com',[a['alias']['canonical_text'] for a in p['profile']['aliases']])
  other=store.login('friend','play-money-only')[2]['id']
  from server import APIError
  with self.assertRaises(APIError):store.create_request(other,'kotik',10000,'blocked','privacy-test-request')
