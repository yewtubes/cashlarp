from datetime import datetime, timezone
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch
from xml.etree import ElementTree

import client_shell
import seasonal_branding


class SeasonalBrandingTests(unittest.TestCase):
    def test_one_time_utc_window_ends_at_november(self):
        for stamp, expected in [('2026-09-30T23:59:59+00:00',False),
                                ('2026-10-01T00:00:00+00:00',True),
                                ('2026-10-31T23:59:59+00:00',True),
                                ('2026-11-01T00:00:00+00:00',False),
                                ('2027-10-26T12:00:00+00:00',False)]:
            config=seasonal_branding.configuration(datetime.fromisoformat(stamp))
            self.assertEqual(expected,config['startsAt'] <= config['serverTime'] < config['endsAt'])
        self.assertEqual('2026-11-01T00:00:00+00:00',seasonal_branding.END.isoformat())

    def test_cached_shell_gets_a_fresh_clock_for_both_applications(self):
        for app in ['login','account']:
            for now in [datetime(2026,10,31,23,59,tzinfo=timezone.utc),datetime(2026,11,1,tzinfo=timezone.utc)]:
                config=seasonal_branding.configuration(now)
                with patch('seasonal_branding.configuration',return_value=config):
                    document=client_shell.seasonal_document(app)
                actual=json.loads(re.search(r'window.cashlarpSeasonalConfig=(.*?);</script>',document)[1])
                self.assertEqual(config,actual)
                self.assertLess(document.index('/local/seasonal.js'),document.index('/local/branding.js'))

    def test_seasonal_assets_are_transparent_self_contained_svg(self):
        folder=Path(__file__).resolve().parents[1]/'local/brand/halloween'
        for path in folder.glob('*.svg'):
            root=ElementTree.fromstring(path.read_text())
            self.assertEqual('{http://www.w3.org/2000/svg}svg',root.tag)
            self.assertNotIn('https://',path.read_text())
        self.assertTrue((folder/'icon-generated.png').is_file())
        self.assertNotIn('#00D64B',(folder/'cashlarp-wordmark.svg').read_text())
