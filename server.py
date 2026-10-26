#!/usr/bin/env python3
"""Local play-money backend and captured-client host. Python 3.10+, no packages."""
import argparse
import base64
import binascii
import csv
import io
import hashlib
import hmac
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs, quote
import client_shell
import profile_photos
import personal_data
import compat
import native_auth
from server_errors import AuthError

ROOT = Path(__file__).resolve().parent
INITIAL_CENTS = 5_000_000_000
MAX_CENTS = 100_000_000_000_000
CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; "
       "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
       "font-src 'self' data:; connect-src 'self'; frame-src 'none'; "
       "object-src 'none'; base-uri 'self'; form-action 'self'")


class APIError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def validate_amount(value):
    if type(value) is not int or not 0 < value <= MAX_CENTS:
        raise APIError(400, "amount_cents must be a positive integer within the balance limit")
    return value


def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1).hex()


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL,
                    display_name TEXT NOT NULL, salt TEXT NOT NULL, password_hash TEXT NOT NULL,
                    balance_cents INTEGER NOT NULL CHECK(balance_cents >= 0));
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id),
                    csrf TEXT NOT NULL, expires INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS transfers (
                    id TEXT PRIMARY KEY, sender TEXT REFERENCES users(id),
                    recipient TEXT REFERENCES users(id), amount_cents INTEGER NOT NULL,
                    note TEXT NOT NULL, idempotency_key TEXT NOT NULL,
                    created_at INTEGER NOT NULL, UNIQUE(sender, idempotency_key));
                CREATE TABLE IF NOT EXISTS ledger (
                    id INTEGER PRIMARY KEY, user_id TEXT REFERENCES users(id),
                    transfer_id TEXT REFERENCES transfers(id), delta_cents INTEGER NOT NULL,
                    kind TEXT NOT NULL, created_at INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS pending_actions (
                    token TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),path TEXT NOT NULL,
                    body TEXT NOT NULL,result TEXT,expires INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS login_flows (
                    token TEXT PRIMARY KEY,alias TEXT NOT NULL,kind TEXT NOT NULL,
                    user_id TEXT REFERENCES users(id),stage TEXT NOT NULL,expires INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id TEXT PRIMARY KEY REFERENCES users(id),json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS alias_challenges (
                    token TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),kind TEXT NOT NULL,
                    alias TEXT NOT NULL,expires INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS profile_photos (
                    user_id TEXT PRIMARY KEY REFERENCES users(id),mime_type TEXT NOT NULL,
                    digest TEXT NOT NULL,image BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS card_designs (
                    user_id TEXT PRIMARY KEY REFERENCES users(id),theme TEXT NOT NULL,
                    include_cashtag INTEGER NOT NULL,image BLOB NOT NULL,touch_data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS activation_flows (
                    token TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),expires INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS preferences (
                    user_id TEXT PRIMARY KEY REFERENCES users(id),cashtag TEXT UNIQUE NOT NULL,
                    public_enabled INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS exports (
                    id TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),csv_text TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS trades (
                    id TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),idempotency_key TEXT NOT NULL,
                    cents INTEGER NOT NULL,buy INTEGER NOT NULL,sats INTEGER NOT NULL,
                    UNIQUE(user_id,idempotency_key));
                CREATE TABLE IF NOT EXISTS extras (
                    user_id TEXT PRIMARY KEY REFERENCES users(id), card_enabled INTEGER NOT NULL DEFAULT 1,
                    btc_sats INTEGER NOT NULL DEFAULT 100000000 CHECK(btc_sats>=0));
                CREATE TABLE IF NOT EXISTS requests (
                    id TEXT PRIMARY KEY, requester TEXT NOT NULL REFERENCES users(id),
                    payer TEXT NOT NULL REFERENCES users(id), amount_cents INTEGER NOT NULL,
                    note TEXT NOT NULL, idempotency_key TEXT NOT NULL, created_at INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending', transfer_id TEXT REFERENCES transfers(id),
                    UNIQUE(requester,idempotency_key));
                CREATE TABLE IF NOT EXISTS savings_accounts (
                    user_id TEXT PRIMARY KEY REFERENCES users(id),
                    balance_cents INTEGER NOT NULL DEFAULT 0 CHECK(balance_cents>=0));
                CREATE TABLE IF NOT EXISTS savings_transfers (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
                    amount_cents INTEGER NOT NULL CHECK(amount_cents>0),
                    direction TEXT NOT NULL CHECK(direction IN ('in','out')),
                    idempotency_key TEXT NOT NULL, created_at INTEGER NOT NULL,
                    ledger_entry_id INTEGER NOT NULL REFERENCES ledger(id),
                    UNIQUE(user_id,idempotency_key));
                CREATE TABLE IF NOT EXISTS balance_changes (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
                    amount_cents INTEGER NOT NULL, kind TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL, created_at INTEGER NOT NULL,
                    UNIQUE(user_id,idempotency_key));
            """)
            if "created_at" not in [r["name"] for r in db.execute("PRAGMA table_info(users)")]:
                db.execute("ALTER TABLE users ADD COLUMN created_at INTEGER NOT NULL DEFAULT 0")
                db.execute("UPDATE users SET created_at=? WHERE created_at=0", (int(time.time()),))
            if "created_at" not in [r["name"] for r in db.execute("PRAGMA table_info(trades)")]:
                db.execute("ALTER TABLE trades ADD COLUMN created_at INTEGER NOT NULL DEFAULT 0")
            if "purpose" not in [r["name"] for r in db.execute("PRAGMA table_info(activation_flows)")]:
                db.execute("ALTER TABLE activation_flows ADD COLUMN purpose TEXT NOT NULL DEFAULT 'ACTIVATE'")
            if "card_activated" not in [r["name"] for r in db.execute("PRAGMA table_info(extras)")]:
                db.execute("ALTER TABLE extras ADD COLUMN card_activated INTEGER NOT NULL DEFAULT 0")
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def register(self, username, password, display_name=None):
        if not isinstance(username, str) or not re.fullmatch(r"[a-z][a-z0-9_]{2,23}", username):
            raise APIError(400, "Use a lowercase sandbox username of 3–24 letters, digits or underscores")
        if not isinstance(password, str) or not 10 <= len(password) <= 128:
            raise APIError(400, "Sandbox password must have 10–128 characters")
        if display_name is not None and (not isinstance(display_name, str) or not 1 <= len(display_name) <= 60):
            raise APIError(400, "Invalid display name")
        salt = secrets.token_bytes(16)
        uid = "sim_" + secrets.token_hex(10)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                if db.execute("SELECT user_id FROM preferences WHERE cashtag=?",(username,)).fetchone():
                    raise APIError(409,"That sandbox name is already reserved")
                db.execute("INSERT INTO users(id,username,display_name,salt,password_hash,balance_cents,created_at) VALUES (?,?,?,?,?,?,?)",
                           (uid, username, display_name or username, salt.hex(),
                            password_hash(password, salt), INITIAL_CENTS, int(time.time())))
                db.execute("INSERT INTO ledger(user_id,delta_cents,kind,created_at) VALUES (?,?,?,?)",
                           (uid, INITIAL_CENTS, "opening_play_money", int(time.time())))
                db.commit()
            except sqlite3.IntegrityError:
                db.rollback()
                raise APIError(409, "Sandbox username already exists")
        return self.user(uid)

    def user(self, uid):
        with self.connect() as db:
            row = db.execute("SELECT id,username,display_name,balance_cents,created_at FROM users WHERE id=?", (uid,)).fetchone()
        if not row:
            raise APIError(404, "Sandbox user not found")
        return dict(row)

    def login(self, username, password):
        if not isinstance(username, str) or not isinstance(password, str) or len(password) > 128:
            raise APIError(401, "Invalid sandbox credentials")
        with self.connect() as db:
            row = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
            salt = bytes.fromhex(row["salt"]) if row else b"\0" * 16
            result = password_hash(password, salt)
            if not row or not hmac.compare_digest(row["password_hash"], result):
                raise APIError(401, "Invalid sandbox credentials")
            token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
            db.execute("DELETE FROM sessions WHERE expires<?", (int(time.time()),))
            db.execute("INSERT INTO sessions VALUES (?,?,?,?)",
                       (hashlib.sha256(token.encode()).hexdigest(), row["id"], csrf, int(time.time()) + 86400))
        return token, csrf, self.user(row["id"])

    def issue_session(self,uid):
        self.user(uid)
        token,csrf=secrets.token_urlsafe(32),secrets.token_urlsafe(24)
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE expires<?",(int(time.time()),))
            db.execute("INSERT INTO sessions VALUES(?,?,?,?)",(hashlib.sha256(token.encode()).hexdigest(),uid,csrf,int(time.time())+86400))
        return token,csrf,self.user(uid)

    def find_alias(self,kind,alias):
        with self.connect() as db:
            users=db.execute("SELECT id,username FROM users").fetchall()
            settings={r["user_id"]:json.loads(r["json"]) for r in db.execute("SELECT * FROM user_settings")}
        for user in users:
            aliases=settings.get(user["id"],{}).get("aliases",[{"type":"EMAIL","canonical_text":user["username"]+"@example.com"}])
            if any(a["type"]==kind and a["canonical_text"].lower()==alias.lower() for a in aliases):return user["id"]
            if kind=="EMAIL" and alias.lower()==user["username"]+"@sandbox.invalid":return user["id"]
        return None

    def session(self, token):
        with self.connect() as db:
            row = db.execute("SELECT user_id,csrf FROM sessions WHERE token_hash=? AND expires>?",
                             (hashlib.sha256(token.encode()).hexdigest(), int(time.time()))).fetchone()
        if not row:
            raise APIError(401, "Sign in to the sandbox first")
        return dict(row)

    def validate_payment(self, amount, note, key):
        validate_amount(amount)
        if not isinstance(note, str) or len(note) > 280:
            raise APIError(400, "Note must be at most 280 characters")
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", key):
            raise APIError(400, "An idempotency key of 8–100 letters, digits, underscores or hyphens is required")

    def _transfer(self, db, sender, recipient_username, amount, note, key):
        recipient = db.execute("SELECT id,balance_cents FROM users WHERE username=?", (recipient_username,)).fetchone()
        if not recipient:
            raise APIError(404, "Sandbox recipient not found")
        if recipient["id"] == sender:
            raise APIError(400, "Choose another sandbox user")
        existing = db.execute("SELECT * FROM transfers WHERE sender=? AND idempotency_key=?", (sender, key)).fetchone()
        if existing:
            if (existing["recipient"], existing["amount_cents"], existing["note"]) != (recipient["id"], amount, note):
                raise APIError(409, "Idempotency key already used for a different payment")
            return dict(existing), False
        if recipient["balance_cents"] + amount > MAX_CENTS:
            raise APIError(400, "Recipient balance limit reached")
        debit = db.execute("UPDATE users SET balance_cents=balance_cents-? WHERE id=? AND balance_cents>=?", (amount, sender, amount))
        if debit.rowcount != 1:
            raise APIError(409, "Insufficient balance")
        db.execute("UPDATE users SET balance_cents=balance_cents+? WHERE id=?", (amount, recipient["id"]))
        tid, now = "sim_pay_" + secrets.token_hex(12), int(time.time())
        db.execute("INSERT INTO transfers VALUES (?,?,?,?,?,?,?)", (tid, sender, recipient["id"], amount, note, key, now))
        for uid, delta in [(sender, -amount), (recipient["id"], amount)]:
            db.execute("INSERT INTO ledger(user_id,transfer_id,delta_cents,kind,created_at) VALUES (?,?,?,?,?)", (uid, tid, delta, "simulated_payment", now))
        return dict(db.execute("SELECT * FROM transfers WHERE id=?", (tid,)).fetchone()), True

    def transfer(self, sender, recipient_username, amount, note, key):
        self.validate_payment(amount, note, key)
        if not isinstance(recipient_username, str):
            raise APIError(400, "Recipient username required")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                result = self._transfer(db, sender, recipient_username, amount, note, key)
                db.commit()
                return result
            except Exception:
                db.rollback()
                raise

    def create_request(self, uid, payer_username, amount, note, key):
        self.validate_payment(amount, note, key)
        if not isinstance(payer_username, str):
            raise APIError(400, "Payer username required")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                payer = db.execute("SELECT id FROM users WHERE username=?", (payer_username,)).fetchone()
                if not payer:
                    raise APIError(404, "Sandbox user not found")
                if payer["id"] == uid:
                    raise APIError(400, "Choose another sandbox user")
                existing = db.execute("SELECT * FROM requests WHERE requester=? AND idempotency_key=?", (uid,key)).fetchone()
                if existing:
                    if (existing["payer"],existing["amount_cents"],existing["note"]) != (payer["id"],amount,note):
                        raise APIError(409, "Idempotency key already used for a different request")
                    db.commit()
                    return dict(existing), False
                if self.settings(payer["id"])["incoming_request_policy"]=="DENY_ALL":
                    raise APIError(403,"This sandbox player is not accepting requests")
                rid = "sim_req_" + secrets.token_hex(12)
                db.execute("INSERT INTO requests(id,requester,payer,amount_cents,note,idempotency_key,created_at) VALUES (?,?,?,?,?,?,?)", (rid,uid,payer["id"],amount,note,key,int(time.time())))
                result = dict(db.execute("SELECT * FROM requests WHERE id=?",(rid,)).fetchone())
                db.commit()
                return result, True
            except Exception:
                db.rollback()
                raise

    def requests(self, uid):
        with self.connect() as db:
            return [dict(r) for r in db.execute("""
                SELECT q.*,r.username requester_username,p.username payer_username
                FROM requests q JOIN users r ON q.requester=r.id JOIN users p ON q.payer=p.id
                WHERE requester=? OR payer=? ORDER BY q.created_at DESC,q.rowid DESC
            """,(uid,uid))]

    def resolve_request(self, uid, rid, action):
        if action not in ("pay", "decline", "cancel") or not isinstance(rid,str):
            raise APIError(400, "Choose pay, decline or cancel")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute("SELECT q.*,u.username FROM requests q JOIN users u ON q.requester=u.id WHERE q.id=?",(rid,)).fetchone()
                if not row or uid not in (row["requester"],row["payer"]):
                    raise APIError(404, "Sandbox request not found")
                actor = row["requester"] if action == "cancel" else row["payer"]
                if uid != actor:
                    raise APIError(403, "This request action belongs to the other player")
                target = {"pay":"paid","cancel":"cancelled","decline":"declined"}[action]
                if row["status"] != "pending":
                    if row["status"] != target:
                        raise APIError(409, "Request is already " + row["status"])
                else:
                    tid = None
                    if action == "pay":
                        payment,_ = self._transfer(db,uid,row["username"],row["amount_cents"],row["note"],"request-"+rid)
                        tid = payment["id"]
                    db.execute("UPDATE requests SET status=?,transfer_id=? WHERE id=?",(target,tid,rid))
                result = dict(db.execute("SELECT * FROM requests WHERE id=?",(rid,)).fetchone())
                db.commit()
                return result
            except Exception:
                db.rollback()
                raise

    def savings_balance(self, uid):
        with self.connect() as db:
            row = db.execute("SELECT balance_cents FROM savings_accounts WHERE user_id=?", (uid,)).fetchone()
            return row["balance_cents"] if row else 0

    def transfer_savings(self, uid, amount, direction, key):
        self.validate_payment(amount, "", key)
        if direction not in ("in", "out"):
            raise APIError(400, "Choose a Savings transfer direction")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                previous = db.execute("SELECT * FROM savings_transfers WHERE user_id=? AND idempotency_key=?", (uid,key)).fetchone()
                if previous:
                    if (previous["amount_cents"],previous["direction"]) != (amount,direction):
                        raise APIError(409, "Idempotency key already used for another Savings transfer")
                    db.commit()
                    return dict(previous),False
                db.execute("INSERT OR IGNORE INTO savings_accounts(user_id) VALUES(?)", (uid,))
                cash_delta = -amount if direction == "in" else amount
                cash = db.execute("UPDATE users SET balance_cents=balance_cents+? WHERE id=? AND balance_cents+? BETWEEN 0 AND ?", (cash_delta,uid,cash_delta,MAX_CENTS))
                savings = db.execute("UPDATE savings_accounts SET balance_cents=balance_cents-? WHERE user_id=? AND balance_cents-? BETWEEN 0 AND ?", (cash_delta,uid,cash_delta,MAX_CENTS))
                if cash.rowcount != 1 or savings.rowcount != 1:
                    raise APIError(409, "Insufficient balance or balance limit exceeded")
                tid,now = "sim_savings_transfer_"+secrets.token_hex(12),int(time.time())
                ledger = db.execute("INSERT INTO ledger(user_id,delta_cents,kind,created_at) VALUES(?,?,?,?)", (uid,cash_delta,"savings_"+direction,now))
                db.execute("INSERT INTO savings_transfers VALUES(?,?,?,?,?,?,?)", (tid,uid,amount,direction,key,now,ledger.lastrowid))
                result = dict(db.execute("SELECT * FROM savings_transfers WHERE id=?", (tid,)).fetchone())
                db.commit()
                return result,True
            except Exception:
                db.rollback()
                raise

    def change_balance(self, uid, amount, kind, key):
        self.validate_payment(amount, "", key)
        if kind not in ("add", "withdraw"):
            raise APIError(400, "Choose add or withdraw")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute("SELECT * FROM balance_changes WHERE user_id=? AND idempotency_key=?",(uid,key)).fetchone()
                if row:
                    if (row["amount_cents"],row["kind"]) != (amount,kind):
                        raise APIError(409,"Idempotency key already used for a different balance change")
                    db.commit()
                    return dict(row),False
                delta = amount if kind == "add" else -amount
                updated = db.execute("UPDATE users SET balance_cents=balance_cents+? WHERE id=? AND balance_cents+? BETWEEN 0 AND ?",(delta,uid,delta,MAX_CENTS))
                if updated.rowcount != 1:
                    raise APIError(409,"Insufficient balance or balance limit exceeded")
                eid,now = "sim_balance_event_"+secrets.token_hex(12),int(time.time())
                db.execute("INSERT INTO balance_changes VALUES(?,?,?,?,?,?)",(eid,uid,amount,kind,key,now))
                db.execute("INSERT INTO ledger(user_id,delta_cents,kind,created_at) VALUES(?,?,?,?)",(uid,delta,"simulated_"+kind,now))
                result = dict(db.execute("SELECT * FROM balance_changes WHERE id=?",(eid,)).fetchone())
                db.commit()
                return result,True
            except Exception:
                db.rollback()
                raise

    def receipt(self, uid, tid):
        with self.connect() as db:
            row = db.execute("""SELECT t.*,s.username sender_username,r.username recipient_username,
              s.display_name sender_name,r.display_name recipient_name FROM transfers t
              JOIN users s ON s.id=t.sender JOIN users r ON r.id=t.recipient
              WHERE t.id=? AND (t.sender=? OR t.recipient=?)""", (tid,uid,uid)).fetchone()
        if not row:
            raise APIError(404,"Sandbox payment not found")
        return dict(row)

    def update_profile(self, uid, name):
        if not isinstance(name,str) or not 1 <= len(name.strip()) <= 60 or any(ord(c)<32 for c in name):
            raise APIError(400,"Display name must contain 1–60 printable characters")
        with self.connect() as db:
            db.execute("UPDATE users SET display_name=? WHERE id=?",(name.strip(),uid))
        return self.user(uid)

    def ledger(self, uid):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT id,transfer_id,delta_cents,kind,created_at FROM ledger WHERE user_id=? ORDER BY id",(uid,))]

    def preferences(self,uid):
        user=self.user(uid)
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO preferences(user_id,cashtag) VALUES(?,?)",(uid,user["username"]))
            return dict(db.execute("SELECT * FROM preferences WHERE user_id=?",(uid,)).fetchone())

    def handle_status(self,uid,handle):
        if not isinstance(handle,str) or not re.fullmatch(r"[a-z][a-z0-9_]{2,23}",handle):
            return "INVALID_CASHTAG"
        with self.connect() as db:
            occupied=db.execute("SELECT id FROM users WHERE username=? AND id!=?",(handle,uid)).fetchone()
            chosen=db.execute("SELECT user_id FROM preferences WHERE cashtag=? AND user_id!=?",(handle,uid)).fetchone()
        return "UNAVAILABLE" if occupied or chosen else "AVAILABLE"

    def set_handle(self,uid,handle):
        self.preferences(uid)
        if self.handle_status(uid,handle)!="AVAILABLE":raise APIError(409,"Choose an available sandbox cashtag")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT id FROM users WHERE username=? AND id!=?",(handle,uid)).fetchone():
                db.rollback();raise APIError(409,"Sandbox cashtag is already taken")
            try:
                db.execute("UPDATE preferences SET cashtag=? WHERE user_id=?",(handle,uid))
                db.commit()
            except sqlite3.IntegrityError:raise APIError(409,"Sandbox cashtag is already taken")

    def set_public(self,uid,enabled):
        if type(enabled) is not bool:raise APIError(400,"Boolean setting required")
        self.preferences(uid)
        with self.connect() as db:db.execute("UPDATE preferences SET public_enabled=? WHERE user_id=?",(int(enabled),uid))

    def extras(self,uid):
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO extras(user_id) VALUES(?)",(uid,))
            return dict(db.execute("SELECT * FROM extras WHERE user_id=?",(uid,)).fetchone())

    def pending_action(self,uid,token):
        if not isinstance(token,str):return None
        with self.connect() as db:row=db.execute("SELECT * FROM pending_actions WHERE token=? AND user_id=? AND expires>?",(token,uid,int(time.time()))).fetchone()
        return dict(row) if row else None

    def start_action(self,uid,path,body):
        token="sim_action_"+secrets.token_urlsafe(24)
        body={k:v for k,v in body.items() if not k.startswith("_sandbox_")}
        with self.connect() as db:db.execute("INSERT INTO pending_actions VALUES(?,?,?,?,?,?)",(token,uid,path,json.dumps(body),None,int(time.time())+900))
        return token

    def finish_action(self,uid,token,result):
        with self.connect() as db:db.execute("UPDATE pending_actions SET result=? WHERE token=? AND user_id=?",(json.dumps(result),token,uid))

    def settings(self,uid):
        defaults={"aliases":[{"type":"EMAIL","canonical_text":self.user(uid)["username"]+"@example.com","verified":True}],
                  "postal_address":{},"incoming_request_policy":"ALLOW_ALL","require_passcode_confirmation":False,
                  "has_passcode":True,"notifications":{}}
        with self.connect() as db:row=db.execute("SELECT json FROM user_settings WHERE user_id=?",(uid,)).fetchone()
        return {**defaults,**(json.loads(row["json"]) if row else {})}

    def update_settings(self,uid,**values):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT json FROM user_settings WHERE user_id=?",(uid,)).fetchone()
            settings=json.loads(row["json"]) if row else {}
            settings.update(values)
            db.execute("INSERT INTO user_settings VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET json=excluded.json",(uid,json.dumps(settings)))
            db.commit()
        return self.settings(uid)

    def check_pin(self,uid,pin):
        config=self.settings(uid)
        if not isinstance(pin,str) or not re.fullmatch(r"[0-9]{4}",pin):return False
        if not config.get("pin_hash"):return hmac.compare_digest(pin,"1234")
        return hmac.compare_digest(password_hash(pin,bytes.fromhex(config["pin_salt"])),config["pin_hash"])

    def set_pin(self,uid,pin,old_pin=None):
        if not isinstance(pin,str) or not re.fullmatch(r"[0-9]{4}",pin):raise APIError(400,"Use four sandbox PIN digits")
        config=self.settings(uid)
        if config["has_passcode"] and not self.check_pin(uid,old_pin):raise APIError(400,"Invalid existing sandbox PIN")
        salt=secrets.token_bytes(16)
        self.update_settings(uid,pin_salt=salt.hex(),pin_hash=password_hash(pin,salt),has_passcode=True,require_passcode_confirmation=True)

    def begin_alias(self,uid,kind,alias):
        if kind=="EMAIL":
            valid=isinstance(alias,str) and re.fullmatch(r"[a-zA-Z0-9._+-]{1,60}@(sandbox\.invalid|example\.(com|net|org))",alias)
        else:valid=isinstance(alias,str) and re.fullmatch(r"\+120255501[0-9]{2}",alias)
        if not valid:raise APIError(400,"Use an example.com email or fictional +12025550100–0199 phone number")
        token="sim_alias_"+secrets.token_urlsafe(24)
        with self.connect() as db:db.execute("INSERT INTO alias_challenges VALUES(?,?,?,?,?)",(token,uid,kind,alias,int(time.time())+900))
        return token

    def verify_alias(self,uid,kind,alias,code):
        if code!="123456":raise APIError(400,"Use sandbox verification code 123456")
        with self.connect() as db:
            row=db.execute("SELECT token FROM alias_challenges WHERE user_id=? AND kind=? AND alias=? AND expires>?",(uid,kind,alias,int(time.time()))).fetchone()
        if not row:raise APIError(400,"Start local verification again")
        owner=self.find_alias(kind,alias)
        if owner is not None and owner!=uid:raise APIError(409,"That alias belongs to another local player")
        config=self.settings(uid);aliases=config["aliases"]
        if not any(a["type"]==kind and a["canonical_text"]==alias for a in aliases):aliases.append({"type":kind,"canonical_text":alias,"verified":True})
        self.update_settings(uid,aliases=aliases)
        with self.connect() as db:db.execute("DELETE FROM alias_challenges WHERE user_id=? AND kind=? AND alias=?",(uid,kind,alias))

    def card_design(self,uid):
        with self.connect() as db:
            row=db.execute("SELECT theme,include_cashtag FROM card_designs WHERE user_id=?",(uid,)).fetchone()
            return dict(row) if row else {"theme":"BLACK","include_cashtag":False}

    def save_card_design(self,uid,theme,image,include_cashtag,touch_data):
        if theme not in {t["id"] for t in compat.themes()} or not isinstance(image,str) or len(image)>4000000:
            raise APIError(400,"Choose an available local card style")
        if type(include_cashtag) is not bool or not isinstance(touch_data,dict):
            raise APIError(400,"Invalid local card customization")
        try:png=base64.b64decode(image,validate=True)
        except (ValueError,binascii.Error):raise APIError(400,"PNG image required")
        if not png.startswith(b"\x89PNG\r\n\x1a\n") or len(png)>3000000:
            raise APIError(400,"Small PNG image required")
        with self.connect() as db:
            db.execute("INSERT INTO card_designs VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET theme=excluded.theme,include_cashtag=excluded.include_cashtag,image=excluded.image,touch_data=excluded.touch_data",(uid,theme,int(include_cashtag),png,json.dumps(touch_data)))

    def start_activation(self,uid,purpose="ACTIVATE"):
        token="sim_activation_"+secrets.token_urlsafe(24)
        with self.connect() as db:
            db.execute("DELETE FROM activation_flows WHERE expires<?",(int(time.time()),))
            db.execute("INSERT INTO activation_flows(token,user_id,expires,purpose) VALUES(?,?,?,?)",(token,uid,int(time.time())+900,purpose))
        return token

    def activate_card(self,uid,token,code):
        if not isinstance(token,str) or code!="123456":raise APIError(400,"Use demo activation code 123456 for the fictional card")
        self.extras(uid)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT user_id FROM activation_flows WHERE token=? AND user_id=? AND expires>? AND purpose='ACTIVATE'",(token,uid,int(time.time()))).fetchone()
            if not row:
                db.rollback();raise APIError(403,"Open the local card activation flow first")
            db.execute("UPDATE extras SET card_activated=1,card_enabled=1 WHERE user_id=? AND card_activated=0",(uid,))
            db.commit()

    def unlock_card(self,uid,token,pin):
        with self.connect() as db:
            row=db.execute("SELECT user_id FROM activation_flows WHERE token=? AND user_id=? AND expires>? AND purpose='UNLOCK'",(token,uid,int(time.time()))).fetchone()
            if not row:raise APIError(403,"Open the sandbox card unlock flow first")
        if not self.check_pin(uid,pin):return False
        self.set_card(uid,True)
        return True

    def set_card(self,uid,enabled):
        self.extras(uid)
        with self.connect() as db:
            db.execute("UPDATE extras SET card_enabled=? WHERE user_id=?",(int(enabled),uid))

    def exchange(self,uid,cents,buy,key):
        self.validate_payment(cents,"",key)
        self.extras(uid)
        # Fixed fictional quote: $100,000 / BTC. One cent = ten satoshis.
        sats=cents*10
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                old=db.execute("SELECT * FROM trades WHERE user_id=? AND idempotency_key=?",(uid,key)).fetchone()
                if old:
                    if (old["cents"],bool(old["buy"])) != (cents,buy):
                        raise APIError(409,"Trade key already used with different details")
                    db.commit()
                    return self.extras(uid)
                delta=-cents if buy else cents
                btc_delta=sats if buy else -sats
                if db.execute("UPDATE users SET balance_cents=balance_cents+? WHERE id=? AND balance_cents+? BETWEEN 0 AND ?",(delta,uid,delta,MAX_CENTS)).rowcount != 1:
                    raise APIError(409,"Insufficient balance or balance limit exceeded")
                if db.execute("UPDATE extras SET btc_sats=btc_sats+? WHERE user_id=? AND btc_sats+? BETWEEN 0 AND 100000000000000000",(btc_delta,uid,btc_delta)).rowcount != 1:
                    raise APIError(409,"Insufficient fictional Bitcoin or holdings limit exceeded")
                db.execute("INSERT INTO trades(id,user_id,idempotency_key,cents,buy,sats,created_at) VALUES(?,?,?,?,?,?,?)",("sim_trade_"+secrets.token_hex(12),uid,key,cents,int(buy),sats,int(time.time())))
                db.execute("INSERT INTO ledger(user_id,delta_cents,kind,created_at) VALUES(?,?,?,?)",(uid,delta,"simulated_btc_buy" if buy else "simulated_btc_sell",int(time.time())))
                db.commit()
            except Exception:
                db.rollback();raise
        return self.extras(uid)

    def profile_photo_url(self, uid):
        return profile_photos.photo_url(self, uid)

    def set_profile_photo(self, uid, encoded, mime_type):
        return profile_photos.save(self, uid, encoded, mime_type)

    def financial_events(self,uid):
        with self.connect() as db:
            changes=[{"id":r["id"],"delta":r["amount_cents"] if r["kind"]=="add" else -r["amount_cents"],
                      "label":"Added money" if r["kind"]=="add" else "Withdrew money",
                      "category":"ADC_TRANSFERS","created_at":r["created_at"]} for r in db.execute("SELECT * FROM balance_changes WHERE user_id=?",(uid,))]
            trades=[{"id":r["id"],"delta":-r["cents"] if r["buy"] else r["cents"],
                     "label":"Bought fictional Bitcoin" if r["buy"] else "Sold fictional Bitcoin",
                     "category":"ADC_BITCOIN","created_at":r["created_at"]} for r in db.execute("SELECT * FROM trades WHERE user_id=?",(uid,))]
            savings=[{"id":r["id"],"delta":-r["amount_cents"] if r["direction"]=="in" else r["amount_cents"],
                      "label":"Moved to Savings" if r["direction"]=="in" else "Moved from Savings",
                      "category":"ADC_SAVINGS","created_at":r["created_at"]} for r in db.execute("SELECT * FROM savings_transfers WHERE user_id=?",(uid,))]
        return changes+trades+savings

    def activity(self, uid):
        with self.connect() as db:
            return [dict(r) for r in db.execute("""
                SELECT t.id,t.amount_cents,t.note,t.created_at,
                       CASE WHEN t.sender=? THEN 'sent' ELSE 'received' END direction,
                       CASE WHEN t.sender=? THEN r.username ELSE s.username END counterparty
                FROM transfers t JOIN users s ON s.id=t.sender JOIN users r ON r.id=t.recipient
                WHERE t.sender=? OR t.recipient=? ORDER BY t.created_at DESC,t.rowid DESC
            """, (uid, uid, uid, uid))]


class Handler(BaseHTTPRequestHandler):
    server_version = "PlayMoneySandbox/0.1"

    def send(self, status, body, content_type="application/json", extra=None):
        extra = dict(extra or {})
        if "Set-Cookie" in extra and os.environ.get("CASHLARP_SECURE_COOKIES") == "1":
            if "; Secure" not in extra["Set-Cookie"]:
                extra["Set-Cookie"] += "; Secure"
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(status)
        for key, value in {
            "Content-Type": content_type, "Content-Length": str(len(body)),
            "Cache-Control": "no-store", "Content-Security-Policy": CSP,
            "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            **(extra or {})
        }.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    @property
    def store(self):
        return self.server.store

    def auth(self, mutate=False):
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get("Cookie", ""))
        except Exception:
            raise APIError(401, "Invalid sandbox session")
        session = self.store.session(cookies["sandbox_session"].value if "sandbox_session" in cookies else "")
        if mutate and not hmac.compare_digest(self.headers.get("X-Sandbox-CSRF", ""), session["csrf"]):
            raise APIError(403, "Invalid sandbox CSRF token")
        return session

    def hosting_access(self):
        password = os.environ.get("CASHLARP_ACCESS_PASSWORD", "")
        if not password:
            return True
        expected_user = os.environ.get("CASHLARP_ACCESS_USER", "cashlarp")
        try:
            scheme, encoded = self.headers.get("Authorization", "").split(" ", 1)
            if scheme.lower() != "basic":
                raise ValueError("Unsupported authentication")
            username, supplied = base64.b64decode(encoded, validate=True).decode().split(":", 1)
            valid = (hmac.compare_digest(username.encode(), expected_user.encode()) &
                     hmac.compare_digest(supplied.encode(), password.encode()))
        except (ValueError, UnicodeError, binascii.Error):
            valid = False
        if not valid:
            self.close_connection = True
            self.send(401, {"error": "Private Cashlarp instance"}, extra={
                "WWW-Authenticate": 'Basic realm="Cashlarp", charset="UTF-8"',
                "Connection": "close"})
        return valid

    def do_GET(self):
        try:
            if not self.hosting_access():
                return
            path = urlsplit(self.path).path
            if path == "/cash-app/personal-data":
                uid=self.auth()["user_id"]
                return self.send(200,personal_data.export(self.store,uid),extra={"Content-Disposition":'attachment; filename="cashlarp-personal-data.json"'})
            if path == "/cash-app/postcard/get-card-theme-configs":
                self.auth();return self.send(200,{"card_themes":compat.themes()})
            if path == "/cash-app/config/stamps-config":
                self.auth()
                catalog=json.loads((ROOT / "capture/config/stamps-config.json").read_text())
                catalog["stamps"] += [json.loads(p.read_text()) for p in sorted((ROOT / "local/stamps").glob("*.json"))]
                return self.send(200,catalog)
            if path in ("/favicon.ico", "/favicon.png", "/apple-touch-icon.png", "/favicon.svg"):
                name = path.removeprefix("/")
                return self.send(200, (ROOT / "local/brand" / name).read_bytes(), mimetypes.guess_type(name)[0] or "image/x-icon")
            if path.startswith("/local-profile-photo/"):
                self.auth()
                match = re.fullmatch(r"/local-profile-photo/(sim_[a-f0-9]+)/([a-f0-9]{16})\.(png|jpg)", path)
                if not match:
                    raise APIError(404, "Profile photo not found")
                with self.store.connect() as db:
                    row = db.execute("SELECT image,mime_type FROM profile_photos WHERE user_id=? AND digest=?", (match[1], match[2])).fetchone()
                if not row:
                    raise APIError(404, "Profile photo not found")
                return self.send(200, row["image"], row["mime_type"])
            if path.startswith("/cdn/local-card-design/"):
                path=path.removeprefix("/cdn")
            if path.startswith("/local-card-design/"):
                uid=self.auth()["user_id"]
                if path!="/local-card-design/"+uid+".png":raise APIError(404,"Card design not found")
                with self.store.connect() as db:row=db.execute("SELECT image FROM card_designs WHERE user_id=?",(uid,)).fetchone()
                if not row:raise APIError(404,"Card design not found")
                return self.send(200,row["image"],"image/png")
            if path == "/cash-app/business-accounts/documents":
                self.auth()
                return self.send(200,{"forms":[]})
            if path.startswith("/static/"):
                path="/cdn"+path
            if path.startswith("/sandbox/player/"):
                return self.send(302,b"",extra={"Location":"/account/pay-and-request"})
            if path == "/support":
                return self.send(302, b"", extra={"Location": "/account/not-found"})
            if path in ("/about", "/sandbox", "/sandbox/status", "/signup"):
                return self.send(302, b"", extra={"Location": "/login"})
            if path == "/api/health":
                return self.send(200, {"ok": True, "mode": "play_money", "client": "captured_login_and_account",
                                       "account_client_captured": True})
            if path == "/api/me":
                s = self.auth()
                return self.send(200, {"user": self.store.user(s["user_id"]), "csrf": s["csrf"], "require_pin":self.store.settings(s["user_id"])["require_passcode_confirmation"], "mode": "play_money"})
            if path == "/api/activity":
                s = self.auth()
                return self.send(200, {"activity": self.store.activity(s["user_id"]), "mode": "play_money"})
            if path == "/api/requests":
                return self.send(200, {"requests": self.store.requests(self.auth()["user_id"]), "mode":"play_money"})
            if path == "/api/users":
                uid = self.auth()["user_id"]
                with self.store.connect() as db:
                    users = [dict(r) for r in db.execute("SELECT id,username,display_name FROM users WHERE id!=? ORDER BY username",(uid,))]
                return self.send(200,{"users":users})
            if path == "/api/ledger":
                return self.send(200,{"ledger":self.store.ledger(self.auth()["user_id"]),"mode":"play_money"})
            if path.startswith("/api/receipts/"):
                return self.send(200,{"receipt":self.store.receipt(self.auth()["user_id"],path.rsplit("/",1)[1]),"mode":"play_money"})
            if path == "/api/statement.csv":
                uid = self.auth()["user_id"]
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(["CASHLARP — SIMULATED TRANSACTIONS — NOT A BANK STATEMENT"])
                writer.writerow(["entry","unix_time","kind","fictional_cents","transfer"])
                for row in self.store.ledger(uid):
                    writer.writerow([row["id"],row["created_at"],row["kind"],row["delta_cents"],row["transfer_id"] or ""])
                return self.send(200,output.getvalue(),"text/csv; charset=utf-8",{"Content-Disposition":'attachment; filename="cashlarp-ledger.csv"'})
            if path == "/":
                return self.send(302, b"", extra={"Location": "/login"})
            if path == "/login":
                try:
                    session = self.auth()
                except APIError:
                    session = None
                if session and not self.store.settings(session["user_id"]).get("onboarding_stage"):
                    requested = parse_qs(urlsplit(self.path).query).get("redirect", ["/account/money"])[0]
                    target = requested if requested.startswith(("/account/", "/dl/", "/web/", "/treehouse/")) and not any(c in requested for c in ("\\", "\r", "\n")) else "/account/money"
                    return self.send(302, b"", extra={"Location": target})
                return self.send(200, client_shell.login_document(), "text/html; charset=utf-8")
            if path == "/account" or path.startswith(("/account/", "/dl/", "/web/", "/treehouse/")):
                try:
                    session = self.auth()
                except APIError:
                    return self.send(302, b"", extra={"Location": "/login?redirect=" + quote(self.path, safe="")})
                if self.store.settings(session["user_id"]).get("onboarding_stage"):
                    return self.send(302, b"", extra={"Location": "/login"})
                html = client_shell.account_document(session)
                return self.send(200, html, "text/html; charset=utf-8")
            prefix, base = ("/cdn/", ROOT / "capture/cdn") if path.startswith("/cdn/") else ("/local/", ROOT / "local")
            if path.startswith("/local/") and (path.lower().endswith(".html") or path == "/local/status.js"):
                raise APIError(404, "Page is not part of the captured client")
            if not path.startswith(prefix):
                raise APIError(404, "Local route not implemented")
            file = (base / path[len(prefix):]).resolve()
            if not file.is_relative_to(base.resolve()) or not file.is_file():
                raise APIError(404, "Captured asset not available")
            return self.send(200, file.read_bytes(), mimetypes.guess_type(file.name)[0] or "application/octet-stream")
        except APIError as e:
            self.send(e.status, {"error": e.message, "mode": "play_money"})

    def do_POST(self):
        try:
            if not self.hosting_access():
                return
            origin = self.headers.get("Origin")
            if origin and urlsplit(origin).netloc != self.headers.get("Host"):
                raise APIError(403, "Cross-origin requests are not allowed")
            length = int(self.headers.get("Content-Length", "0"))
            body_limit=5000000 if urlsplit(self.path).path in ("/2.0/cash/set-card-customization", "/2.0/cash/set-profile-photo") else 16384
            if not 0 < length <= body_limit:
                raise APIError(400, "A small JSON request body is required")
            try:
                data = json.loads(self.rfile.read(length))
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise APIError(400, "Invalid JSON")
            if not isinstance(data, dict):
                raise APIError(400, "JSON object required")
            path = urlsplit(self.path).path
            if path == "/2.0/cash/get-flow" and os.environ.get("CASHLARP_DEBUG_NATIVE") == "1":
                print("Native flow request:", json.dumps(data), flush=True)
            if path == "/2.0/cash/web/device-info":
                # Compatibility no-op. Device fingerprint payload is discarded.
                return self.send(200, {"mode": "play_money"})
            auth_paths={"/2.0/cash/register-email","/2.0/cash/register-sms","/2.0/cash/verify-email","/2.0/cash/verify-sms","/2.0/cash/set-full-name","/2.0/cash/set-cashtag"}
            if path in auth_paths:
                try:existing_session=self.auth()
                except APIError:existing_session=None
                cookies = SimpleCookie(self.headers.get("Cookie", ""))
                flow_token = cookies["sandbox_login"].value if "sandbox_login" in cookies else ""
                with self.store.connect() as db:
                    login_flow = db.execute("SELECT stage FROM login_flows WHERE token=? AND expires>?", (flow_token, int(time.time()))).fetchone()
                pending_signup = existing_session and self.store.settings(existing_session["user_id"]).get("onboarding_stage")
                active_login_flow = login_flow and login_flow["stage"] != "COMPLETE"
                if existing_session is None or pending_signup or (active_login_flow and path not in ("/2.0/cash/register-email", "/2.0/cash/register-sms")):
                    native=native_auth.dispatch(path,data,self.store,self.headers.get("Cookie",""))
                    if native is not None:
                        result,headers=native
                        return self.send(200,result,extra=headers)
            if path in ("/2.0/cash/web/cdp", "/2.0/cash/cdp-track-event","/2.0/cash/record-completed-journey","/2.0/cash/record-completed-journey-batch","/cash-app/user-journeys/record-completed-journey"):
                return self.send(200,{})
            if path == "/api/register":
                user = self.store.register(data.get("username"), data.get("password"), data.get("display_name"))
                return self.send(201, {"user": user, "mode": "play_money"})
            if path == "/api/session":
                token, csrf, user = self.store.login(data.get("username"), data.get("password"))
                cookie = "sandbox_session=" + token + "; HttpOnly; SameSite=Strict; Path=/; Max-Age=86400"
                if self.headers.get("X-Forwarded-Proto") == "https":
                    cookie += "; Secure"
                return self.send(200, {"user": user, "csrf": csrf, "mode": "play_money"}, extra={"Set-Cookie": cookie})
            if path in ("/api/logout", "/logout"):
                self.auth(mutate=True)
                cookies = SimpleCookie(self.headers.get("Cookie", ""))
                digest = hashlib.sha256(cookies["sandbox_session"].value.encode()).hexdigest()
                with self.store.connect() as db:
                    db.execute("DELETE FROM sessions WHERE token_hash=?", (digest,))
                    if "sandbox_login" in cookies:
                        db.execute("DELETE FROM login_flows WHERE token=?", (cookies["sandbox_login"].value,))
                return self.send(200, {"ok": True}, extra={"Set-Cookie": "sandbox_session=; Max-Age=0; HttpOnly; SameSite=Strict; Path=/"})
            if path == "/api/profile":
                uid = self.auth(mutate=True)["user_id"]
                return self.send(200,{"user":self.store.update_profile(uid,data.get("display_name")),"mode":"play_money"})
            if path == "/api/balance":
                uid = self.auth(mutate=True)["user_id"]
                if self.store.settings(uid)["require_passcode_confirmation"] and not self.store.check_pin(uid,data.get("pin")):
                    raise APIError(403,"Enter your local sandbox PIN")
                result,created = self.store.change_balance(uid,data.get("amount_cents"),data.get("kind"),self.headers.get("Idempotency-Key"))
                return self.send(201 if created else 200,{"change":result,"mode":"play_money"})
            if path == "/api/requests":
                uid = self.auth(mutate=True)["user_id"]
                result,created = self.store.create_request(uid,data.get("payer"),data.get("amount_cents"),data.get("note",""),self.headers.get("Idempotency-Key"))
                return self.send(201 if created else 200,{"request":result,"mode":"play_money"})
            if path == "/api/requests/resolve":
                uid = self.auth(mutate=True)["user_id"]
                if data.get("action")=="pay" and self.store.settings(uid)["require_passcode_confirmation"] and not self.store.check_pin(uid,data.get("pin")):
                    raise APIError(403,"Enter your local sandbox PIN")
                return self.send(200,{"request":self.store.resolve_request(uid,data.get("id"),data.get("action")),"mode":"play_money"})
            if path == "/api/transfers":
                s = self.auth(mutate=True)
                if self.store.settings(s["user_id"])["require_passcode_confirmation"] and not self.store.check_pin(s["user_id"],data.get("pin")):
                    raise APIError(403,"Enter your local sandbox PIN")
                transfer, created = self.store.transfer(s["user_id"], data.get("recipient"),
                    data.get("amount_cents"), data.get("note", ""), self.headers.get("Idempotency-Key"))
                return self.send(201 if created else 200, {"transfer": transfer, "mode": "play_money"})
            if path.startswith(("/2.0/cash/", "/cash-app/")):
                session = self.auth(mutate=True)
                data["_sandbox_pin_authorized"]=False
                data["_sandbox_flow_token"]=self.headers.get("Cash-Flow-Token", "")
                response = compat.read_rpc(path, data, self.store, session["user_id"])
                if response is not None:
                    return self.send(200, response, "text/csv; charset=UTF-8" if isinstance(response,str) else "application/json",extra={"Cash-Flow-Token":response["token"]} if isinstance(response,dict) and response.get("token") else None)
            # Never proxy a captured RPC to Cash App, including login/OTP endpoints.
            raise APIError(501, "Original-client RPC not implemented locally: " + path)
        except (APIError, compat.CompatibilityError, AuthError) as e:
            self.send(e.status, {"error": e.message, "mode": "play_money"})
        except (ValueError, OverflowError):
            self.send(400, {"error": "Malformed request", "mode": "play_money"})


def make_server(host, port, db_path):
    server = ThreadingHTTPServer((host, port), Handler)
    server.store = Store(db_path)
    return server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 3000)))
    parser.add_argument("--db", default=str(ROOT / "data/sandbox.sqlite3"))
    parser.add_argument("--strictPort", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    server = make_server(args.host, args.port, args.db)
    print(f"Play-money sandbox: http://{args.host}:{server.server_port} — original client with local fictional balances", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
