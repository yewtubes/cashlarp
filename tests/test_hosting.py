import base64
import http.client
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fixtures import DEMO_PASSWORD, make_server
from scripts.backup import backup
from tools.configure_host import configure


class HostingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_configuration_is_private_and_never_replaces_credentials(self):
        destination = self.root / '.env'
        configure('CASHLARP.Example.com', destination)
        original = destination.read_text()
        self.assertIn('DOMAIN=cashlarp.example.com\n', original)
        self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
        self.assertGreater(len(original.split('CASHLARP_ACCESS_PASSWORD=')[1].splitlines()[0]), 40)
        with self.assertRaises(FileExistsError):
            configure('other.example.com', destination)
        self.assertEqual(original, destination.read_text())
        for domain in ('https://example.com', 'foo\nBAR=1', 'localhost', 'a..com', '-bad.example'):
            with self.subTest(domain=domain), self.assertRaises(ValueError):
                configure(domain, self.root / 'invalid')

    def test_backup_includes_wal_and_refuses_to_overwrite(self):
        source, target = self.root / 'live.sqlite3', self.root / 'backup.sqlite3'
        with sqlite3.connect(source) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE data (value TEXT)')
            db.execute("INSERT INTO data VALUES ('saved')")
            db.commit()
            backup(source, target)
        with sqlite3.connect(target) as db:
            self.assertEqual(db.execute('SELECT value FROM data').fetchone()[0], 'saved')
        with self.assertRaises(FileExistsError):
            backup(source, target)
        with self.assertRaises(FileNotFoundError):
            backup(self.root / 'missing', self.root / 'empty')
        self.assertFalse((self.root / 'empty').exists())

    def test_private_gate_covers_assets_health_and_mutations(self):
        with patch.dict('os.environ', {'CASHLARP_ACCESS_PASSWORD': 'hosting-password', 'CASHLARP_ACCESS_USER': 'owner', 'CASHLARP_SECURE_COOKIES': '1'}):
            server = make_server('127.0.0.1', 0, self.root / 'http.sqlite3')
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            def request(method, path, body=None, authorization=None):
                conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                headers = {'Content-Type': 'application/json'}
                if authorization:
                    headers['Authorization'] = authorization
                conn.request(method, path, json.dumps(body) if body is not None else None, headers)
                response = conn.getresponse()
                result = response.status, dict(response.getheaders()), response.read()
                conn.close()
                return result
            try:
                for path in ('/login', '/api/health', '/local/branding.js'):
                    status, headers, _ = request('GET', path)
                    self.assertEqual(status, 401)
                    self.assertIn('Basic', headers['WWW-Authenticate'])
                self.assertEqual(request('POST', '/api/register', {'username': 'blocked', 'password': 'long-password'})[0], 401)
                for value in ('Bearer ignored', 'Basic !!!', 'Basic ' + base64.b64encode(b'owner:wrong').decode()):
                    self.assertEqual(request('GET', '/api/health', authorization=value)[0], 401)
                auth = 'Basic ' + base64.b64encode(b'owner:hosting-password').decode()
                self.assertEqual(request('GET', '/api/health', authorization=auth)[0], 200)
                status, headers, _ = request('POST', '/api/session', {'username': 'kotik', 'password': DEMO_PASSWORD}, auth)
                self.assertEqual(status, 200)
                self.assertIn('; Secure', headers['Set-Cookie'])
                status, headers, _ = request('POST', '/2.0/cash/register-email', {'email_address': 'kotik@example.com'}, auth)
                self.assertEqual(status, 200)
                self.assertIn('; Secure', headers['Set-Cookie'])
                self.assertEqual(request('GET', '/.env', authorization=auth)[0], 404)
                self.assertEqual(request('GET', '/.git/config', authorization=auth)[0], 404)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_launcher_builds_and_passes_through_cli_options(self):
        project = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, '-B', str(project / 'run.py'), '--help'], cwd=self.root, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--db', result.stdout)
        self.assertIn('--host', result.stdout)
