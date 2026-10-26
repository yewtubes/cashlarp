from pathlib import Path
import tempfile
import unittest
import compat
from fixtures import Store
from server import APIError


class LocalJourneyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'journeys.db')
        self.uid=self.store.login('kotik','play-money-only')[2]['id']
        self.other=self.store.login('friend','play-money-only')[2]['id']
    def tearDown(self):self.tmp.cleanup()
    def rpc(self,path,data):return compat.read_rpc(path,data,self.store,self.uid)
    def goal(self,amount,token):
        return self.rpc('/2.0/cash/submit-form',{'action_id':'sim_save_savings_goal','_sandbox_flow_token':token,'results':[{'id':'goal_amount','text_input_result':{'input_field_values':[amount]}}]})
    def test_goal_updates_native_progress_and_can_be_removed(self):
        self.store.transfer_savings(self.uid,9950,'in','goal-seed-money')
        token=self.rpc('/2.0/cash/get-flow',{'initiation_data':'SET_SAVINGS_GOAL'})['token']
        self.goal('500',token);self.goal('500',token)
        overview=self.rpc('/cash-app/savings/get-savings-overview',{})
        folder=next(f for f in overview['versioned_savings_folders']['v2_folders'] if 'goal_folder' in f)
        self.assertEqual(50000,folder['goal_folder']['goal_amount']['amount'])
        self.assertEqual(9950,sum(f['balance']['amount'] for f in overview['versioned_savings_folders']['v2_folders']))
        self.assertEqual(9950,self.store.savings_balance(self.uid))
        token=self.rpc('/2.0/cash/get-flow',{'initiation_data':'SET_SAVINGS_GOAL'})['token']
        self.goal('0',token)
        self.assertIsNone(self.store.settings(self.uid)['savings_goal_cents'])
    def test_goal_rejects_unowned_wrong_flow_and_invalid_values(self):
        token=self.store.start_activation(self.other,'SAVINGS_GOAL')
        with self.assertRaises(APIError):self.goal('500',token)
        token=self.store.start_activation(self.uid,'ROUNDUPS')
        with self.assertRaises(APIError):self.goal('500',token)
        token=self.store.start_activation(self.uid,'SAVINGS_GOAL')
        for amount in ['-1','1.234','NaN','1000000000001']:
            with self.assertRaises(compat.CompatibilityError):self.goal(amount,token)
        self.assertIsNone(self.store.settings(self.uid).get('savings_goal_cents'))
    def test_roundups_preferences_are_scoped_and_do_not_move_money(self):
        before=self.store.user(self.uid)['balance_cents']
        for action,enabled in [('sim_roundups_on',True),('sim_roundups_off',False)]:
            token=self.rpc('/2.0/cash/get-flow',{'initiation_data':'PIGGYBANK_SAVINGS_ROUND_UP'})['token']
            self.rpc('/2.0/cash/submit-form',{'action_id':action,'_sandbox_flow_token':token})
            self.assertEqual(enabled,self.store.settings(self.uid)['round_ups_enabled'])
        self.assertEqual(before,self.store.user(self.uid)['balance_cents'])
        self.assertEqual(0,self.store.savings_balance(self.uid))
    def test_card_replacement_uses_scenario_header_and_is_exactly_once(self):
        self.store.activate_card(self.uid,self.store.start_activation(self.uid),'123456')
        first=self.rpc('/2.0/cash/get-profile',{})['profile']['issued_card']
        response=self.rpc('/2.0/cash/complete-scenario',{'_sandbox_client_scenario':'REPORT_LOST_CARD'})
        self.assertEqual(first['last_four'],self.rpc('/2.0/cash/get-profile',{})['profile']['issued_card']['last_four'])
        for _ in range(2):self.rpc('/2.0/cash/submit-form',{'action_id':'sim_replace_card','_sandbox_flow_token':response['token']})
        card=self.rpc('/2.0/cash/get-profile',{})['profile']['issued_card']
        self.assertFalse(card['activated']);self.assertNotEqual(first['last_four'],card['last_four'])
        self.assertEqual(1,self.store.extras(self.uid)['card_generation'])
        self.store.activate_card(self.uid,self.store.start_activation(self.uid),'123456')
        self.assertTrue(self.rpc('/2.0/cash/get-profile',{})['profile']['issued_card']['activated'])
    def test_replacement_rejects_foreign_and_wrong_tokens(self):
        for token in [self.store.start_activation(self.other,'REPLACE_CARD'),self.store.start_activation(self.uid,'ACTIVATE')]:
            with self.assertRaises(APIError):self.store.replace_card(self.uid,token)
        self.assertEqual(0,self.store.extras(self.uid)['card_generation'])
