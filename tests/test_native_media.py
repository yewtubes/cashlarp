import base64
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from fixtures import DEMO_PASSWORD, make_server
from server import Store

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jq1kAAAAASUVORK5CYII=')


class NativeMediaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)/'test.sqlite3'
        self.server = make_server('127.0.0.1',0,self.path)
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.token,self.csrf,self.user = self.server.store.login('kotik',DEMO_PASSWORD)

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()

    def request(self, method, path, data=None, authenticated=True):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
        headers={'Content-Type':'application/json'}
        if authenticated:headers.update({'Cookie':'sandbox_session='+self.token,'X-Sandbox-CSRF':self.csrf})
        connection.request(method,path,json.dumps(data) if data is not None else None,headers)
        response=connection.getresponse();result=response.status,dict(response.getheaders()),response.read();connection.close();return result

    def test_original_photo_upload_persistence_and_removal(self):
        status,_,raw=self.request('POST','/2.0/cash/set-profile-photo',{'image_data':'data:image/png;base64,'+base64.b64encode(PNG).decode(),'mime_type':'image/png'})
        self.assertEqual(200,status);url=json.loads(raw)['image_url']
        self.assertEqual(url,Store(self.path).profile_photo_url(self.user['id']))
        status,headers,raw=self.request('GET',url)
        self.assertEqual(200,status);self.assertEqual('image/png',headers['Content-Type']);self.assertEqual(PNG,raw)
        profile=json.loads(self.request('POST','/2.0/cash/get-profile',{})[2])['profile']
        self.assertEqual(url,profile['photo_url'])
        self.assertEqual(401,self.request('GET',url,authenticated=False)[0])
        self.assertEqual(200,self.request('POST','/2.0/cash/clear-profile-photo',{})[0])
        self.assertEqual(404,self.request('GET',url)[0])

    def test_photo_validation_and_mime_detection(self):
        # Source file MIME and canvas MIME can differ in the original client.
        url=self.server.store.set_profile_photo(self.user['id'],'data:image/png;base64,'+base64.b64encode(PNG).decode(),'image/jpeg')
        self.assertEqual('image/png',self.request('GET',url)[1]['Content-Type'])
        for image in ('not-base64','data:image/svg+xml;base64,PHN2Zz4=',base64.b64encode(b'<svg/>').decode()):
            self.assertEqual(400,self.request('POST','/2.0/cash/set-profile-photo',{'image_data':image,'mime_type':'image/png'})[0])

    def test_favicons_and_original_savings_contract(self):
        for route,signature in (('/favicon.png',b'\x89PNG'),('/favicon.ico',b'\x00\x00\x01\x00'),('/apple-touch-icon.png',b'\x89PNG')):
            status,_,data=self.request('GET',route,authenticated=False)
            self.assertEqual(200,status);self.assertTrue(data.startswith(signature))
        self.assertIn(b'href="/favicon.png"',self.request('GET','/login',authenticated=False)[2])
        overview=json.loads(self.request('POST','/cash-app/savings/get-savings-overview',{})[2])
        self.assertEqual('SAVINGS_CUSTOMER_STATUS_ADOPTED',overview['customer']['customer_status'])
        self.assertEqual('USD',overview['balance']['amount']['currency_code'])
        self.assertIn('general_folder',overview['versioned_savings_folders']['v2_folders'][0])
        eligibility=json.loads(self.request('POST','/cash-app/business-accounts/get-c4b-eligibility',{})[2])
        self.assertFalse(eligibility['money_btc_applet']['is_eligible'])
