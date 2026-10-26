"""Integration checks for the original client's observed RPC wire format."""
import json
from pathlib import Path
import tempfile
import threading
import http.client
import unittest

from server import INITIAL_CENTS
from fixtures import DEMO_PASSWORD, make_server


class NativeClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.server = make_server("127.0.0.1", 0, Path(self.tmp.name) / "native.sqlite3")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.sender = self.login("kotik")
        self.receiver = self.login("friend")

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def request(self, method, path, data=None, session=None):
        headers = {}
        if session:
            headers = {"Cookie": session["cookie"], "X-Sandbox-CSRF": session["csrf"]}
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        conn.request(method, path, None if data is None else json.dumps(data), headers)
        response = conn.getresponse()
        status, response_headers, body = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return status, response_headers, body

    def login(self, username):
        status, headers, raw = self.request("POST", "/api/session", {"username": username, "password": DEMO_PASSWORD})
        self.assertEqual(200, status)
        session = json.loads(raw)
        session["cookie"] = headers["Set-Cookie"].split(";")[0]
        return session

    def rpc(self, path, data=None, session=None):
        status, _, raw = self.request("POST", path, data or {}, session or self.sender)
        return status, json.loads(raw)

    def payment(self, **overrides):
        body = {
            "external_id": "web-account-test-native-0001",
            "payment_getters": [{"id": self.receiver["user"]["id"], "cashtag": "friend"}],
            "orientation": "CASH",
            "instrument_selection": {"instrument_token": "sim_balance_" + self.sender["user"]["id"],
                                     "accepted_fee_amount": {"amount": 0, "currency_code": "USD"}},
            "amount": {"amount": "2500000", "currency_code": "USD"},
            "note": "Original client test",
        }
        body.update(overrides)
        return self.rpc("/2.0/cash/initiate-payment", body)

    def test_native_wire_payment_updates_both_profiles_and_activity(self):
        status, response = self.payment()
        self.assertEqual(200, status)
        result = response["response_context"]
        self.assertEqual("SHOW_DIALOG", result["status_result"]["action"])
        self.assertEqual("PAY_SCREEN", result["status_result"]["primary_button"]["action"])
        self.assertEqual([], result["scenario_plan"]["blocker_descriptors"])
        for session, expected, prefix in [(self.sender, INITIAL_CENTS - 2500000, "−"),
                                          (self.receiver, INITIAL_CENTS + 2500000, "+")]:
            _, data = self.rpc("/2.0/cash/get-profile", {"customer_token": "ignored-untrusted-value"}, session)
            self.assertEqual(session["user"]["id"], data["profile"]["customer_token"])
            self.assertEqual(expected, data["profile"]["instruments"][0]["available_balance"]["amount"])
            _, data = self.rpc("/cash-app/activity/v1.0/page", {}, session)
            row = data["activity_rows"][0]
            self.assertEqual(result["payments"][0]["token"], row["row_id"])
            self.assertTrue(row["payment_history_inputs_row"]["payment"]["history_data"]["amount_formatted_activity_list"].startswith(prefix))
        _, duplicate = self.payment()
        self.assertEqual(result["payments"], duplicate["response_context"]["payments"])
        self.assertEqual(INITIAL_CENTS - 2500000, self.server.store.user(self.sender["user"]["id"])["balance_cents"])

    def test_native_payment_rejects_wrong_currency_instrument_and_invalid_amount(self):
        self.assertEqual(400, self.payment(amount={"amount": "10000", "currency_code": "BTC"})[0])
        self.assertEqual(400, self.payment(instrument_selection={"instrument_token": "real-bank"})[0])
        for value in ["-100", "100.5", True, "1e6", "1" * 100]:
            with self.subTest(value=value):
                self.assertEqual(400, self.payment(amount={"amount": value, "currency_code": "USD"})[0])
        self.assertEqual(INITIAL_CENTS, self.server.store.user(self.sender["user"]["id"])["balance_cents"])

    def test_native_payment_duplicate_conflict_and_overdraft_preserve_balances(self):
        self.assertEqual(200, self.payment()[0])
        self.assertEqual(409, self.payment(note="Changed retry payload")[0])
        self.assertEqual(409, self.payment(external_id="web-account-overdraft-0001",
            amount={"amount": str(INITIAL_CENTS + 1), "currency_code": "USD"})[0])

    def test_bootstrap_uses_original_account_scripts_and_session(self):
        status, headers, body = self.request("GET", "/account/money", session=self.sender)
        self.assertEqual(200, status)
        self.assertIn(b'id="root"', body)
        self.assertIn(b'content="/cdn/web/account/', body)
        self.assertIn(b"main.fa6baaec96a82623.js", body)
        self.assertIn(self.sender["user"]["id"].encode(), body)
        self.assertNotIn(b"__SANDBOX_", body)
        self.assertNotIn(DEMO_PASSWORD.encode(), body)
        self.assertIn("connect-src 'self'", headers["Content-Security-Policy"])
        self.assertEqual(401, self.rpc("/2.0/cash/get-profile", session={"cookie": "", "csrf": ""})[0])
        self.assertEqual(501, self.rpc("/2.0/cash/some-unknown-rpc")[0])


if __name__ == "__main__":
    unittest.main()
