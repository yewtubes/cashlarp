"""Savings conservation, isolation, retry and native PIN contracts."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
import compat
from fixtures import Store
from server import APIError, INITIAL_CENTS, MAX_CENTS

IN='/cash-app/internal-transfers/v1.0/add-cash'
OUT='/cash-app/internal-transfers/v1.0/move-cash'


class SavingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'savings.db'
        self.store=Store(self.path)
        self.uid=self.store.login('kotik','play-money-only')[2]['id']
        self.other=self.store.login('friend','play-money-only')[2]['id']

    def tearDown(self):self.tmp.cleanup()

    def body(self,cents=12500,key='savings-native-key'):
        return {'external_id':key,'amount':{'amount':str(cents),'currency_code':'USD'},
                'savings_balance_token':'sim_savings_'+self.uid,
                'target_cash_balance_token':'sim_balance_'+self.uid,
                'main_cash_balance_snapshot':{'instrument_token':'sim_balance_'+self.uid},
                'transfer_context':{'home':{}}}

    def rpc(self,path,data):return compat.read_rpc(path,data,self.store,self.uid)

    def assert_balances(self,cash,savings):
        self.assertEqual(cash,self.store.user(self.uid)['balance_cents'])
        self.assertEqual(savings,self.store.savings_balance(self.uid))
        self.assertEqual(INITIAL_CENTS,cash+savings)
        self.assertEqual(cash,sum(row['delta_cents'] for row in self.store.ledger(self.uid)))

    def test_native_round_trip_persists_and_is_visible_in_activity(self):
        self.rpc(IN,self.body())
        self.rpc(OUT,self.body(2550,'savings-native-out'))
        self.assert_balances(INITIAL_CENTS-9950,9950)
        self.store=Store(self.path)
        overview=self.rpc('/cash-app/savings/get-savings-overview',{})
        self.assertEqual(9950,overview['balance']['amount']['amount'])
        self.assertEqual(9950,overview['versioned_savings_folders']['v2_folders'][0]['balance']['amount'])
        events=compat.activity_rows(self.store,self.uid,'Savings')
        self.assertEqual(2,len(events))
        self.assertEqual([],compat.activity_rows(self.store,self.other,'Savings'))
        self.assertEqual(0,self.store.savings_balance(self.other))
        with self.store.connect() as db:
            self.assertEqual(2,db.execute('SELECT count(*) FROM savings_transfers s JOIN ledger l ON s.ledger_entry_id=l.id WHERE s.user_id=?',(self.uid,)).fetchone()[0])

    def test_savings_activity_filters_other_events_and_reverses_cash_direction(self):
        self.rpc(IN,self.body())
        self.store.change_balance(self.uid,100,"add","funding-not-savings")
        request={"activity_token":{"activity_token_type":"CUSTOMER_TOKEN_SAVINGS_ACCOUNT","token":self.uid}}
        row=self.rpc('/cash-app/activity/v1.0/page',request)['activity_rows'][0]
        self.assertEqual(1,len(self.rpc('/cash-app/activity/v1.0/page',request)['activity_rows']))
        payment=row['payment_history_inputs_row']['payment']
        self.assertEqual('RECIPIENT',payment['role'])
        self.assertEqual('+$125.00',payment['history_data']['amount_formatted_activity_list'])
        self.assertEqual('ADC_SAVINGS',payment['display_category'])
        receipt=self.rpc('/cash-app/activity/v1.0/get',{**request,'activityItemGlobalId':{'activity_row_id':row['row_id']}})
        self.assertEqual('RECIPIENT',receipt['activityRow']['payment_history_inputs_row']['payment']['role'])

    def test_duplicate_requests_and_conflicting_retries(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(lambda _:self.store.transfer_savings(self.uid,12500,'in','same-savings-key'),range(8)))
        self.assertEqual(1,sum(created for _,created in results))
        self.assertEqual(1,len({row['id'] for row,_ in results}))
        for amount,direction in [(12501,'in'),(12500,'out')]:
            with self.assertRaises(APIError):self.store.transfer_savings(self.uid,amount,direction,'same-savings-key')
        self.assert_balances(INITIAL_CENTS-12500,12500)

    def test_overdraft_and_balance_limit_roll_back_both_accounts(self):
        for amount,direction in [(1,'out'),(INITIAL_CENTS+1,'in')]:
            with self.assertRaises(APIError):self.store.transfer_savings(self.uid,amount,direction,'overdraft-'+direction)
        self.assert_balances(INITIAL_CENTS,0)
        self.store.transfer_savings(self.uid,100,'in','seed-savings-key')
        def withdraw(index):
            try:self.store.transfer_savings(self.uid,100,'out','withdraw-key-'+str(index));return True
            except APIError:return False
        with ThreadPoolExecutor(max_workers=2) as pool:self.assertEqual(1,sum(pool.map(withdraw,range(2))))
        self.assert_balances(INITIAL_CENTS,0)
        self.store.transfer_savings(self.uid,100,'in','second-seed-key')
        with self.store.connect() as db:db.execute('UPDATE users SET balance_cents=? WHERE id=?',(MAX_CENTS,self.uid))
        with self.assertRaises(APIError):self.store.transfer_savings(self.uid,1,'out','overflow-savings-key')
        self.assertEqual(MAX_CENTS,self.store.user(self.uid)['balance_cents'])
        self.assertEqual(100,self.store.savings_balance(self.uid))

    def test_foreign_tokens_currency_goals_and_invalid_amounts_rejected(self):
        for field,value in [('savings_balance_token','sim_savings_'+self.other),('target_cash_balance_token','sim_balance_'+self.other),('main_cash_balance_snapshot',{'instrument_token':'sim_balance_'+self.other}),('transfer_context',{'goal_folder':{'goal_token':'unknown'}})]:
            data=self.body();data[field]=value
            with self.assertRaises(compat.CompatibilityError):self.rpc(OUT,data)
        for amount in [True,0,-1,1.2,None,{},'not-money']:
            data=self.body();data['amount']['amount']=amount
            with self.assertRaises(APIError):self.rpc(IN,data)
        data=self.body();data['amount']['currency_code']='EUR'
        with self.assertRaises(compat.CompatibilityError):self.rpc(IN,data)
        self.assert_balances(INITIAL_CENTS,0)

    def test_pin_required_before_transfer_and_replay_is_exactly_once(self):
        self.store.update_settings(self.uid,require_passcode_confirmation=True)
        result=self.rpc(IN,self.body())
        self.assert_balances(INITIAL_CENTS,0)
        token=result['token']
        wrong=self.rpc('/2.0/cash/verify-passcode',{'_sandbox_flow_token':token,'passcode':'0000'})
        self.assertEqual('INVALID_PASSCODE',wrong['status'])
        self.assert_balances(INITIAL_CENTS,0)
        for _ in range(2):self.rpc('/2.0/cash/verify-passcode',{'_sandbox_flow_token':token,'passcode':'1234'})
        self.assert_balances(INITIAL_CENTS-12500,12500)
