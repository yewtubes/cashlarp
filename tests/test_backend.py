import concurrent.futures
import hashlib
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import APIError, INITIAL_CENTS
from fixtures import DEMO_PASSWORD, Store, make_server


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "test.sqlite3")
        _, _, self.sender = self.store.login("kotik", DEMO_PASSWORD)
        _, _, self.recipient = self.store.login("friend", DEMO_PASSWORD)

    def tearDown(self):
        self.tmp.cleanup()

    def pay(self, amount=12345, key="test_payment_001", recipient="friend", note="play money"):
        return self.store.transfer(self.sender["id"], recipient, amount, note, key)

    def assert_error(self, status, action):
        with self.assertRaises(APIError) as error:
            action()
        self.assertEqual(status, error.exception.status)

    def test_balances_persist_and_ledger_balances(self):
        transfer, created = self.pay()
        self.assertTrue(created)
        reopened = Store(self.store.path)
        self.assertEqual(INITIAL_CENTS - 12345, reopened.user(self.sender["id"])["balance_cents"])
        self.assertEqual(INITIAL_CENTS + 12345, reopened.user(self.recipient["id"])["balance_cents"])
        with reopened.connect() as db:
            self.assertEqual(0, db.execute("SELECT SUM(delta_cents) FROM ledger WHERE transfer_id=?", (transfer["id"],)).fetchone()[0])
        self.assertEqual("received", reopened.activity(self.recipient["id"])[0]["direction"])

    def test_retry_does_not_double_pay(self):
        original, _ = self.pay()
        retry, created = self.pay()
        self.assertFalse(created)
        self.assertEqual(original["id"], retry["id"])
        self.assertEqual(INITIAL_CENTS - 12345, self.store.user(self.sender["id"])["balance_cents"])

    def test_reused_key_with_changed_payload_conflicts(self):
        self.pay()
        self.assert_error(409, lambda: self.pay(amount=12346))
        self.assert_error(409, lambda: self.pay(note="different"))

    def test_overdraft_is_atomic(self):
        self.assert_error(409, lambda: self.pay(amount=INITIAL_CENTS + 1))
        self.assertEqual(INITIAL_CENTS, self.store.user(self.sender["id"])["balance_cents"])
        self.assertEqual(INITIAL_CENTS, self.store.user(self.recipient["id"])["balance_cents"])
        self.assertEqual([], self.store.activity(self.sender["id"]))

    def test_amounts_reject_floats_booleans_and_nonpositive_values(self):
        for value in [0, -1, 1.1, True, "100", None, 10**16]:
            with self.subTest(value=value):
                self.assert_error(400, lambda: self.pay(amount=value))

    def test_unknown_and_self_recipient(self):
        self.assert_error(404, lambda: self.pay(recipient="missing"))
        self.assert_error(400, lambda: self.pay(recipient="kotik"))

    def test_concurrent_spends_cannot_overdraw(self):
        def spend(i):
            try:
                self.pay(amount=INITIAL_CENTS, key="concurrent_" + str(i))
                return "paid"
            except APIError as error:
                return error.status
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(spend, [1, 2]))
        self.assertCountEqual(["paid", 409], results)
        self.assertEqual(0, self.store.user(self.sender["id"])["balance_cents"])
        self.assertEqual(INITIAL_CENTS * 2, self.store.user(self.recipient["id"])["balance_cents"])

    def test_invalid_password_and_expired_session(self):
        self.assert_error(401, lambda: self.store.login("kotik", "incorrect_password"))
        token, _, _ = self.store.login("kotik", DEMO_PASSWORD)
        with self.store.connect() as db:
            db.execute("UPDATE sessions SET expires=0 WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))
        self.assert_error(401, lambda: self.store.session(token))

    def test_registration_and_duplicate_names(self):
        user = self.store.register("new_user", "independent-sandbox-password")
        self.assertEqual(INITIAL_CENTS, user["balance_cents"])
        self.assert_error(409, lambda: self.store.register("new_user", "independent-sandbox-password"))
        self.assert_error(400, lambda: self.store.register("real@email.com", "independent-sandbox-password"))


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.server = make_server("127.0.0.1", 0, Path(cls.tmp.name) / "http.sqlite3")
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.tmp.cleanup()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        conn.request(method, path, json.dumps(body) if body is not None else None, headers or {})
        response = conn.getresponse()
        status, response_headers, data = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return status, response_headers, data

    def test_session_required(self):
        status, _, _ = self.request("GET", "/api/me")
        self.assertEqual(401, status)

    def test_http_payment_csrf_and_cross_origin(self):
        status, headers, raw = self.request("POST", "/api/session", {"username": "kotik", "password": DEMO_PASSWORD})
        self.assertEqual(200, status)
        session = json.loads(raw)
        cookie = headers["Set-Cookie"].split(";")[0]
        body = {"recipient": "friend", "amount_cents": 100, "note": "HTTP test"}
        headers = {"Cookie": cookie, "Idempotency-Key": "http_test_001"}
        self.assertEqual(403, self.request("POST", "/api/transfers", body, headers)[0])
        headers["X-Sandbox-CSRF"] = session["csrf"]
        headers["Origin"] = "https://unrelated.invalid"
        self.assertEqual(403, self.request("POST", "/api/transfers", body, headers)[0])
        del headers["Origin"]
        self.assertEqual(201, self.request("POST", "/api/transfers", body, headers)[0])
        self.assertEqual(200, self.request("POST", "/api/transfers", body, headers)[0])
        self.assertEqual(200, self.request("POST", "/api/logout", {}, headers)[0])
        self.assertEqual(401, self.request("GET", "/api/me", headers={"Cookie": cookie})[0])

    def test_original_login_assets_and_isolation(self):
        status, headers, body = self.request("GET", "/login")
        self.assertEqual(200, status)
        self.assertIn("connect-src 'self'", headers["Content-Security-Policy"])
        self.assertIn(b"<title>Cashlarp</title>", body)
        self.assertIn(b"/cdn/web/login/", body)
        self.assertNotIn(b'src="https://', body)
        self.assertEqual(302, self.request("GET", "/")[0])
        self.assertEqual(302, self.request("GET", "/account/money")[0])
        self.assertEqual(401, self.request("POST", "/2.0/cash/verify-email", {"email": "nobody@example.invalid"})[0])
        self.assertEqual(404, self.request("GET", "/local/../../server.py")[0])

    def test_captured_bundles_match_manifest(self):
        root = Path(__file__).resolve().parents[1] / "capture"
        for entry in json.loads((root / "manifest.json").read_text()):
            self.assertNotIn("error", entry)
            self.assertEqual(entry["sha256"], hashlib.sha256((root / entry["path"]).read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
