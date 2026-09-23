"""SQLite accounts, scrypt password hashes and signed, revocable JWT sessions."""
import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
import jwt

SESSION_SECONDS = 3600


class Accounts:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'accounts.sqlite3'
        configured = os.environ.get('ADF_JWT_SECRET')
        if configured and len(configured) < 32:
            raise ValueError('ADF_JWT_SECRET must contain at least 32 characters.')
        keyfile = self.directory / 'jwt.key'
        if not configured:
            try:
                fd = os.open(keyfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(fd, 'w') as stream:
                    stream.write(secrets.token_urlsafe(48))
            except FileExistsError:
                pass
        self.secret = configured or keyfile.read_text().strip()
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL, token_version INTEGER NOT NULL DEFAULT 0)''')
            db.execute('''CREATE TABLE IF NOT EXISTS formatting_profiles (
                id TEXT PRIMARY KEY, owner INTEGER NOT NULL, rules TEXT NOT NULL)''')
        self.dummy_hash = self.hash_password(secrets.token_urlsafe(32))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def hash_password(password, salt=None):
        salt = salt or secrets.token_hex(16)
        derived = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1, maxmem=64*1024*1024)
        return f'scrypt${salt}${derived.hex()}'

    def verify(self, password, encoded):
        try:
            return hmac.compare_digest(self.hash_password(password, encoded.split('$')[1]), encoded)
        except (ValueError, IndexError):
            return False

    def signup(self, username, password):
        password_hash = self.hash_password(password)
        with self.connect() as db:
            cursor = db.execute('INSERT INTO users(username,password_hash) VALUES (?,?)', (username, password_hash))
            return dict(db.execute('SELECT * FROM users WHERE id=?', (cursor.lastrowid,)).fetchone())

    def login(self, username, password):
        with self.connect() as db:
            user = db.execute('SELECT * FROM users WHERE username=? COLLATE NOCASE', (username,)).fetchone()
        valid = self.verify(password, user['password_hash'] if user else self.dummy_hash)
        return dict(user) if user and valid else None

    def token(self, user):
        now = int(time.time())
        return jwt.encode({'sub': str(user['id']), 'ver': user['token_version'], 'iat': now,
                           'exp': now + SESSION_SECONDS, 'iss': 'adf-check', 'aud': 'adf-web'},
                          self.secret, algorithm='HS256')

    def user_from_token(self, token):
        try:
            claims = jwt.decode(token, self.secret, algorithms=['HS256'], audience='adf-web', issuer='adf-check',
                                options={'require': ['sub', 'exp', 'iat', 'ver', 'iss', 'aud']})
            with self.connect() as db:
                user = db.execute('SELECT * FROM users WHERE id=?', (int(claims['sub']),)).fetchone()
            if user and user['token_version'] == claims['ver']:
                return {'id': user['id'], 'username': user['username']}
        except (jwt.InvalidTokenError, ValueError, TypeError):
            pass
        return None

    def revoke(self, user_id):
        with self.connect() as db:
            db.execute('UPDATE users SET token_version=token_version+1 WHERE id=?', (user_id,))
