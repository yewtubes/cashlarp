from pathlib import Path
import tempfile
import unittest
from server import APIError,INITIAL_CENTS
from fixtures import Store
import compat
class EconomyTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'test.db');self.uid=self.store.login('kotik','play-money-only')[2]['id']
 def tearDown(self):self.tmp.cleanup()
 def rpc(self,path,data):return compat.read_rpc(path,data,self.store,self.uid)
 def test_native_funding_validation_and_retry(self):
  b={'source':{'token':'sim_funding_'+self.uid},'target':{'token':'sim_balance_'+self.uid},'amount':{'amount':'500000','currency_code':'USD'},'external_id':'native-funding-key'}
  for _ in range(2):self.rpc('/cash-app/cash-in/v1.0/add-cash',b)
  self.assertEqual(INITIAL_CENTS+500000,self.store.user(self.uid)['balance_cents'])
  b['target']={'token':'other'}
  with self.assertRaises(compat.CompatibilityError):self.rpc('/cash-app/cash-in/v1.0/add-cash',b)
  self.rpc('/cash-app/out/v1.0/initiate-cash-out',{'source':{'token':'sim_balance_'+self.uid},'deposit_preference':'TRANSFER_SLOWLY_WITHOUT_FEE','amount':{'amount':'500000','currency_code':'USD'},'external_id':'native-withdraw-key'})
  self.assertEqual(INITIAL_CENTS,self.store.user(self.uid)['balance_cents'])
 def test_exchange_atomic_retry_and_rollback(self):
  initial=self.store.extras(self.uid)['btc_sats']
  for _ in range(2):self.store.exchange(self.uid,10000,True,'trade-key-first')
  self.assertEqual(initial+100000,self.store.extras(self.uid)['btc_sats'])
  self.assertEqual(INITIAL_CENTS-10000,self.store.user(self.uid)['balance_cents'])
  with self.assertRaises(APIError):self.store.exchange(self.uid,10001,True,'trade-key-first')
  with self.assertRaises(APIError):self.store.exchange(self.uid,INITIAL_CENTS*100,False,'trade-key-overdraft')
  self.assertEqual(INITIAL_CENTS-10000,self.store.user(self.uid)['balance_cents'])
  self.store.exchange(self.uid,10000,False,'trade-key-reverse')
  self.assertEqual(initial,self.store.extras(self.uid)['btc_sats'])
  self.assertEqual(INITIAL_CENTS,sum(r['delta_cents'] for r in self.store.ledger(self.uid)))
 def test_native_card_and_name_persist(self):
  for flow,expected in [('DISABLE_ISSUED_CARD_IN_POSTCARD',False),('ENABLE_ISSUED_CARD',True)]:
   response=self.rpc('/2.0/cash/get-flow',{'initiation_data':flow})
   if expected:
    self.assertFalse(self.rpc('/2.0/cash/web/profile',{})['issued_cash_card']['enabled'])
    token=response['token']
    self.assertEqual('INVALID_PASSCODE',self.rpc('/2.0/cash/verify-passcode',{'passcode':'0000','_sandbox_flow_token':token})['status'])
    self.rpc('/2.0/cash/verify-passcode',{'passcode':'1234','_sandbox_flow_token':token})
   self.assertEqual(expected,self.rpc('/2.0/cash/web/profile',{})['issued_cash_card']['enabled'])
  self.rpc('/2.0/cash/set-full-name',{'full_name':'Roleplay Kotik'})
  self.assertEqual('Roleplay Kotik',self.rpc('/2.0/cash/get-profile',{})['profile']['full_name'])
 def test_filters_exports_and_participant_scope(self):
  self.store.transfer(self.uid,'friend',10000,'Small payment','small-payment-key')
  self.store.transfer(self.uid,'friend',20000,'Large payment','large-payment-key')
  criteria={'free_text_search':'payment','sort':{'sort_by_field':'AMOUNT','order':'ASC'},'filter_groups':[{'filters':[{'amount':{'amount':10000,'comparison':'LESS_THAN_OR_EQUAL_TO'}}]}]}
  rows=self.rpc('/cash-app/activity/v1.0/search',{'request':criteria})['activity_rows']
  self.assertEqual(1,len(rows))
  rid=self.rpc('/cash-app/activity-export/v1.0/create-export',criteria)['request_id']
  raw=self.rpc('/cash-app/activity-export/v1.0/download-export',{'request_id':rid})
  self.assertIn('CASHLARP',raw);self.assertIn('Small payment',raw);self.assertNotIn('Large payment',raw)
  other=self.store.login('friend','play-money-only')[2]['id']
  with self.assertRaises(compat.CompatibilityError):compat.read_rpc('/cash-app/activity-export/v1.0/get-export',{'request_id':rid},self.store,other)
 def test_cashtag_identity_and_original_credentials(self):
  self.rpc('/2.0/cash/set-cashtag',{'cashtag':'billionaire'})
  self.assertEqual('billionaire',self.rpc('/2.0/cash/get-profile',{})['profile']['cashtag'])
  self.assertEqual(self.uid,self.store.login('kotik','play-money-only')[2]['id'])
  other=self.store.login('friend','play-money-only')[2]['id']
  with self.assertRaises(APIError):compat.read_rpc('/2.0/cash/set-cashtag',{'cashtag':'billionaire'},self.store,other)
  self.assertEqual('UNAVAILABLE',self.store.handle_status(other,'billionaire'))

 def test_activation_requires_owned_flow_and_demo_code(self):
  response=self.rpc('/2.0/cash/get-flow',{'initiation_data':'ACTIVATE_PHYSICAL_CARD?params_type=json'})
  token=response['token']
  self.assertFalse(self.store.extras(self.uid)['card_activated'])
  with self.assertRaises(APIError):self.store.activate_card(self.uid,token,'000000')
  other=self.store.login('friend','play-money-only')[2]['id']
  with self.assertRaises(APIError):self.store.activate_card(other,token,'123456')
  self.store.activate_card(self.uid,token,'123456')
  self.assertTrue(self.rpc('/2.0/cash/web/profile',{})['issued_cash_card']['activated'])
  with self.assertRaises(APIError):self.store.unlock_card(self.uid,token,'1234')
 def test_original_card_design_contract_and_persistence(self):
  import base64
  png=base64.b64encode(b'\x89PNG\r\n\x1a\nfixture').decode()
  result=self.rpc('/2.0/cash/get-flow',{'initiation_data':'CHANGE_CARD_DESIGN'})
  descriptor=result['response_context']['scenario_plan']['blocker_descriptors'][0]
  self.assertEqual('card_customization',descriptor['id'])
  options=descriptor['blocker']['card_customization']['card_option_sections'][0]['options']
  self.assertEqual({'BLACK','WHITE','PINK_ID','GLOW_ID'},{o['card_theme']['id'] for o in options})
  self.rpc('/2.0/cash/set-card-customization',{'card_theme_token':'sim_theme_WHITE','image_bytes':png,'include_cashtag':True,'touch_data':{'strokes':[{'test':'stroke'}],'stamps':[],'width':2023,'height':1276}})
  self.assertEqual('WHITE',self.store.card_design(self.uid)['theme'])
  self.assertEqual('WHITE',self.rpc('/2.0/cash/web/profile',{})['issued_cash_card']['card_theme']['id'])
  reopened=Store(self.store.path)
  self.assertEqual('WHITE',reopened.card_design(self.uid)['theme'])
  other=self.store.login('friend','play-money-only')[2]['id']
  self.assertEqual('BLACK',self.store.card_design(other)['theme'])
  with self.assertRaises(APIError):self.store.save_card_design(self.uid,'WHITE','not-base64',True,{})
  with self.assertRaises(APIError):self.store.save_card_design(self.uid,'UNKNOWN',png,True,{})
