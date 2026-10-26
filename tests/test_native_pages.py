"""Fresh-install and original-client routing/authentication regression checks."""
from html.parser import HTMLParser
import http.client
from http.cookies import SimpleCookie
import json
from pathlib import Path
import tempfile
import threading
import unittest

import client_shell
from server import APIError, Store, make_server


class BodyElements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.inside = False
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == "body":
            self.inside = True
        if self.inside:
            self.elements.append((tag, dict(attrs)))

    def handle_endtag(self, tag):
        if tag == "body":
            self.inside = False


class NativePageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "fresh.sqlite3"
        self.server = make_server("127.0.0.1", 0, self.path)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.cookies = {}
        self.csrf = ""

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def request(self, method, path, data=None):
        headers = {"Cookie": "; ".join(k + "=" + v for k, v in self.cookies.items()), "X-Sandbox-CSRF": self.csrf, "Content-Type": "application/json"}
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        connection.request(method, path, json.dumps(data) if data is not None else None, headers)
        response = connection.getresponse()
        status, result_headers, raw = response.status, dict(response.getheaders()), response.read()
        connection.close()
        jar = SimpleCookie(result_headers.get("Set-Cookie", ""))
        for key, value in jar.items():
            if value["max-age"] == "0":
                self.cookies.pop(key, None)
            else:
                self.cookies[key] = value.value
        return status, result_headers, raw

    def rpc(self, path, data):
        status, _, raw = self.request("POST", path, data)
        self.assertEqual(status, 200, raw)
        return json.loads(raw)

    def verify(self, alias="newplayer@example.com", phone=False):
        self.rpc("/2.0/cash/register-" + ("sms" if phone else "email"), {"sms_number" if phone else "email_address": alias})
        result = self.rpc("/2.0/cash/verify-" + ("sms" if phone else "email"), {"sms_number" if phone else "email_address": alias, "sms_verification_code" if phone else "verification_code": "123456"})
        me = json.loads(self.request("GET", "/api/me")[2])
        self.csrf = me["csrf"]
        return result, me["user"]["id"]

    def test_empty_database_stays_empty_on_restart(self):
        for store in (self.server.store, Store(self.path)):
            with store.connect() as db:
                self.assertEqual(0, db.execute("SELECT count(*) FROM users").fetchone()[0])
            for name in ("friend", "kotik"):
                with self.assertRaises(APIError):
                    store.login(name, "play-money-only")

    def test_page_body_comes_from_captured_document(self):
        original = BodyElements((client_shell.ROOT / "capture/login.html").read_text()).elements
        for app in ("login", "account"):
            elements = BodyElements(client_shell.document(app)).elements
            expected = [(tag, {k: ("root" if app == "account" and k == "id" and v == "app-root" else v) for k, v in attrs.items()}) for tag, attrs in original]
            self.assertEqual(expected, elements)
            self.assertFalse(any(tag in ("form", "input", "button") for tag, _ in elements))
        self.assertEqual([], list((client_shell.ROOT / "local").rglob("*.html")))

    def test_custom_page_routes_cannot_serve_replacement_html(self):
        for path in ("/about", "/sandbox", "/sandbox/status", "/signup"):
            status, headers, _ = self.request("GET", path)
            self.assertEqual(302, status)
            self.assertEqual("/login", headers["Location"])
        for path in ("/local/status.html", "/local/about.html", "/local/account.html", "/local/login.html", "/local/brand/preview.html", "/local/status.js"):
            self.assertEqual(404, self.request("GET", path)[0])
        self.assertEqual("/login?redirect=%2Faccount%2Fcard", self.request("GET", "/account/card")[1]["Location"])

    def test_signup_login_redirect_and_native_signout(self):
        _, uid = self.verify()
        self.assertEqual("/login", self.request("GET", "/account/money")[1]["Location"])
        self.rpc("/2.0/cash/set-full-name", {"full_name": "New Player"})
        self.rpc("/2.0/cash/set-cashtag", {"cashtag": "mynewtag"})
        self.assertEqual(200, self.request("GET", "/account/money")[0])
        for native_path in ("/dl/flow/CHANGE_CARD_DESIGN", "/web/view/savings/activity", "/treehouse/activity/receipt/test"):
            status, _, body = self.request("GET", native_path)
            self.assertEqual(200, status)
            self.assertIn(b"main.fa6baaec96a82623.js", body)
        self.assertEqual("/account/card", self.request("GET", "/login?redirect=/account/card")[1]["Location"])
        for target in ("https://elsewhere.invalid", "//elsewhere.invalid", "/account/\\evil", "/account/x%0D%0AInjected:yes"):
            self.assertEqual("/account/money", self.request("GET", "/login?redirect=" + target)[1]["Location"])
        self.rpc("/logout", {})
        self.assertEqual(401, self.request("GET", "/api/me")[0])
        _, again = self.verify()
        self.assertEqual(uid, again)
        with self.server.store.connect() as db:
            self.assertEqual(1, db.execute("SELECT count(*) FROM users").fetchone()[0])

    def test_interrupted_signup_resumes_without_duplicate_identity(self):
        _, uid = self.verify()
        self.cookies.clear()
        result, again = self.verify()
        self.assertEqual(uid, again)
        self.assertIn("name", result["response_context"]["scenario_plan"]["blocker_descriptors"][0]["blocker"])
        self.rpc("/2.0/cash/set-full-name", {"full_name": "Returning Player"})
        result, again = self.verify()
        self.assertEqual(uid, again)
        self.assertIn("cashtag", result["response_context"]["scenario_plan"]["blocker_descriptors"][0]["blocker"])
        self.rpc("/2.0/cash/set-cashtag", {"cashtag": "returningtag"})
        with self.server.store.connect() as db:
            self.assertEqual(1, db.execute("SELECT count(*) FROM users").fetchone()[0])

    def test_sms_signup_and_completed_login_do_not_hijack_contact_editing(self):
        _, uid = self.verify("+12025550137", phone=True)
        self.rpc("/2.0/cash/set-full-name", {"full_name": "Phone Player"})
        self.rpc("/2.0/cash/set-cashtag", {"cashtag": "phonetag"})
        self.rpc("/logout", {})
        _, again = self.verify("+12025550137", phone=True)
        self.assertEqual(uid, again)
        self.rpc("/2.0/cash/register-email", {"email_address": "contact@example.com"})
        self.rpc("/2.0/cash/verify-email", {"email_address": "contact@example.com", "verification_code": "123456"})
        aliases = self.server.store.settings(uid)["aliases"]
        self.assertIn("contact@example.com", [a["canonical_text"] for a in aliases])
