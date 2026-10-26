import json
from pathlib import Path
import tempfile
import time
import unittest
import compat
from fixtures import Store

ROOT=Path(__file__).resolve().parents[1]


class CashlarpCardTests(unittest.TestCase):
    def test_custom_theme_keeps_original_themes_and_monochrome_stamp(self):
        themes=compat.themes()
        self.assertEqual(11,len(themes))
        theme=next(t for t in themes if t['id']=='CASHLARP')
        self.assertEqual('#00D64B',theme['card_color'])
        self.assertEqual('Cashlarp Card',theme['title'])
        descriptor=compat.customization_descriptor()
        self.assertIn('CASHLARP',{o['card_theme']['id'] for s in descriptor['blocker']['card_customization']['card_option_sections'] for o in s['options']})
        stamp=json.loads((ROOT/'local/stamps/benjamin-netanyahu.json').read_text())
        self.assertEqual('Benjamin Netanyahu outline',stamp['accessibility_text'])
        self.assertIn('fill="#000000"',stamp['svg'])
        self.assertNotIn('<image',stamp['svg'])
        self.assertNotIn('#FFFFFF',stamp['svg'])

    def test_per_account_card_suffixes_are_stable_and_issue_date_is_current(self):
        with tempfile.TemporaryDirectory() as temporary:
            store=Store(Path(temporary)/'cards.sqlite3')
            users=[store.login(name,'play-money-only')[2] for name in ('kotik','friend')]
            cards=[compat.card(user,store.extras(user['id'])) for user in users]
            for user,card in zip(users,cards):
                self.assertRegex(card['last_four'],r'^[1-9][0-9]{3}$')
                self.assertEqual(card['last_four'],compat.card(store.user(user['id']),store.extras(user['id']))['last_four'])
                self.assertLess(abs(time.time()-card['issued_at']),10)

    def test_native_flow_type_requests_open_the_real_card_and_address_blockers(self):
        with tempfile.TemporaryDirectory() as temporary:
            store=Store(Path(temporary)/'flows.sqlite3')
            user=store.login('kotik','play-money-only')[2]
            for flow,blocker in [('CHANGE_CARD_DESIGN','card_customization'),('SET_ADDRESS','address')]:
                response=compat.read_rpc('/2.0/cash/get-flow',{'flow_type':flow},store,user['id'])
                self.assertIn(blocker,response['response_context']['scenario_plan']['blocker_descriptors'][0]['blocker'])
