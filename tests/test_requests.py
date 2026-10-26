"""State-machine, authorization and ledger invariants for local requests."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from server import APIError, INITIAL_CENTS
from fixtures import Store
import compat

class RequestTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'test.db')
        self.a=self.store.login('kotik','play-money-only')[2]['id'];self.b=self.store.login('friend','play-money-only')[2]['id']
        self.c=self.store.register('outsider','test-password')['id']
    def tearDown(self):self.tmp.cleanup()
    def create(self,key='request-key-0001'):
        return self.store.create_request(self.a,'friend',125000,'Request test',key)[0]
    def test_concurrent_pay_once_and_conservation(self):
        r=self.create()
        with ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(lambda _:self.store.resolve_request(self.b,r['id'],'pay'),range(8)))
        self.assertEqual(1,len({r['transfer_id'] for r in results}))
        self.assertEqual(INITIAL_CENTS+125000,self.store.user(self.a)['balance_cents'])
        self.assertEqual(INITIAL_CENTS-125000,self.store.user(self.b)['balance_cents'])
        self.assertEqual(1,len(self.store.activity(self.a)))
        for uid in (self.a,self.b):self.assertEqual(self.store.user(uid)['balance_cents'],sum(x['delta_cents'] for x in self.store.ledger(uid)))
    def test_authorization_and_terminal_states(self):
        r=self.create()
        for actor,action in [(self.a,'pay'),(self.a,'decline'),(self.b,'cancel'),(self.c,'pay')]:
            with self.assertRaises(APIError):self.store.resolve_request(actor,r['id'],action)
        self.store.resolve_request(self.b,r['id'],'decline')
        with self.assertRaises(APIError):self.store.resolve_request(self.b,r['id'],'pay')
        self.assertEqual(INITIAL_CENTS,self.store.user(self.b)['balance_cents'])
        r=self.create('request-key-0002');self.store.resolve_request(self.a,r['id'],'cancel')
        with self.assertRaises(APIError):self.store.resolve_request(self.b,r['id'],'pay')
    def test_create_retry_conflict_and_failed_pay_rollback(self):
        r=self.create();self.assertEqual(r,self.create())
        with self.assertRaises(APIError):self.store.create_request(self.a,'friend',125001,'Request test','request-key-0001')
        self.store.change_balance(self.b,INITIAL_CENTS,'withdraw','remove-everything')
        with self.assertRaises(APIError):self.store.resolve_request(self.b,r['id'],'pay')
        self.assertEqual('pending',self.store.requests(self.a)[0]['status'])
        self.assertEqual([],self.store.activity(self.a))
    def test_balance_idempotency_and_receipt_privacy(self):
        for kind in ('add','withdraw'):
            key='balance-key-'+kind
            first=self.store.change_balance(self.a,400,kind,key)
            second=self.store.change_balance(self.a,400,kind,key)
            self.assertTrue(first[1]);self.assertFalse(second[1]);self.assertEqual(first[0],second[0])
        self.assertEqual(INITIAL_CENTS,self.store.user(self.a)['balance_cents'])
        payment,_=self.store.transfer(self.a,'friend',500,'note','payment-key-test')
        with self.assertRaises(APIError):self.store.receipt(self.c,payment['id'])
        self.assertEqual(payment['id'],self.store.receipt(self.b,payment['id'])['id'])
    def test_native_request_receipt_and_confirm(self):
        result=compat.read_rpc('/2.0/cash/initiate-payment',{'payment_getters':[{'id':self.b}],'orientation':'BILL','amount':{'amount':'125000','currency_code':'USD'},'note':'Native request','external_id':'native-request-001'},self.store,self.a)
        rid=result['response_context']['payments'][0]['token']
        row=compat.read_rpc('/cash-app/activity/v1.0/get',{'activityItemGlobalId':{'activity_row_id':rid}},self.store,self.b)['activityRow']
        self.assertEqual('SENDER',row['payment_history_inputs_row']['payment']['role'])
        with self.assertRaises(compat.CompatibilityError):compat.read_rpc('/cash-app/activity/v1.0/get',{'activityItemGlobalId':{'activity_row_id':rid}},self.store,self.c)
        result=compat.read_rpc('/2.0/cash/confirm-payment',{'payment_tokens':[rid]},self.store,self.b)
        self.assertIn('Paid $1,250.00',result['response_context']['status_result']['text'])
        self.assertEqual(INITIAL_CENTS+125000,self.store.user(self.a)['balance_cents'])
