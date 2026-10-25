from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from extract_asset_urls import extract_urls


class CaptureToolTests(unittest.TestCase):
    def test_only_public_static_urls_are_emitted(self):
        base = "https://cash-f.squarecdn.com/web/account/" + "a" * 40
        good = base + "/main.1234.js"
        raw = ('<script src="' + good + '"></script>'
               '<script src="' + good + '?token=secret"></script>'
               '<script src="https://cash.app/2.0/cash/get-profile"></script>'
               '<script src="https://cash-images-f.squarecdn.com/private.png"></script>'
               '<script src="' + base + '/../../secret.js"></script>')
        self.assertEqual([good], extract_urls(raw))

    def test_har_headers_and_account_payload_are_discarded(self):
        import json
        good = "https://cash-f.squarecdn.com/web/account/" + "a" * 40 + "/main.1234.js"
        har = {"log": {"entries": [
            {"request": {"url": good, "headers": [{"name": "Cookie", "value": "secret"}]},
             "response": {"content": {"text": "private value"}}},
            {"request": {"url": "https://cash.app/account"}},
            {"request": {"url": "https://cash.app/2.0/cash/get-profile?token=secret"}}
        ]}}
        self.assertEqual([good], extract_urls(json.dumps(har)))


if __name__ == "__main__":
    unittest.main()
