from pathlib import Path
import http.client
import json
import tempfile
import threading
import unittest
from fixtures import Store, make_server
import compat
import personal_data


class PersonalDataTests(unittest.TestCase):
    def test_export_is_owner_scoped_and_excludes_authentication_material(self):
        with tempfile.TemporaryDirectory() as temporary:
            store=Store(Path(temporary)/'export.db')
            uid=store.login('kotik','play-money-only')[2]['id']
            other=store.login('friend','play-money-only')[2]['id']
            token,csrf,_=store.issue_session(uid)
            store.update_settings(uid,pin_hash='PRIVATE_PIN_HASH',pin_salt='PRIVATE_PIN_SALT',postal_address={'address_line_1':'Owner address'})
            store.update_settings(other,postal_address={'address_line_1':'OTHER_PRIVATE_ADDRESS'})
            store.transfer_savings(uid,10000,'in','export-savings-key')
            store.transfer(other,'kotik',50,'Shared payment','export-payment-key')
            result=personal_data.export(store,uid)
            text=json.dumps(result)
            self.assertEqual(uid,result['account']['id'])
            self.assertEqual(10000,result['savings_balance_cents'])
            self.assertEqual(1,len(result['savings_transfers']))
            self.assertEqual(1,len(result['payments']))
            self.assertEqual('Owner address',result['settings']['postal_address']['address_line_1'])
            for secret in [token,csrf,'PRIVATE_PIN_HASH','PRIVATE_PIN_SALT','OTHER_PRIVATE_ADDRESS','password_hash','pin_hash']:
                self.assertNotIn(secret,text)
            self.assertEqual([],personal_data.export(store,other)['savings_transfers'])

    def test_original_download_url_requires_session_and_returns_attachment(self):
        with tempfile.TemporaryDirectory() as temporary:
            server=make_server('127.0.0.1',0,Path(temporary)/'http.db')
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                connection=http.client.HTTPConnection('127.0.0.1',server.server_port)
                connection.request('GET','/cash-app/personal-data');response=connection.getresponse()
                self.assertEqual(401,response.status);response.read()
                connection.request('POST','/api/session',json.dumps({'username':'kotik','password':'play-money-only'}),{'Content-Type':'application/json'})
                response=connection.getresponse();cookie=response.getheader('Set-Cookie').split(';',1)[0];response.read()
                connection.request('GET','/cash-app/personal-data',headers={'Cookie':cookie})
                response=connection.getresponse()
                self.assertEqual(200,response.status)
                self.assertIn('attachment;',response.getheader('Content-Disposition'))
                self.assertIn('application/json',response.getheader('Content-Type'))
                self.assertEqual('kotik',json.loads(response.read())['account']['username'])
                connection.close()
            finally:server.shutdown();server.server_close();thread.join()

    def test_display_name_button_uses_original_name_blocker(self):
        with tempfile.TemporaryDirectory() as temporary:
            store=Store(Path(temporary)/'name.db')
            uid=store.login('kotik','play-money-only')[2]['id']
            response=compat.read_rpc('/2.0/cash/get-flow',{'initiation_data':'DISPLAY_NAME?params_type=json'},store,uid)
            self.assertIn('name',response['response_context']['scenario_plan']['blocker_descriptors'][0]['blocker'])
