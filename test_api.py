"""End-to-end API tests using isolated SQLite databases and real documents."""
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import jwt
from fastapi.testclient import TestClient
from utilities.api import create_app, COOKIE
from utilities.local_auth import Accounts
from test_project import sample_bytes

HEADERS = {'X-Requested-With':'ADF-Web'}


class APITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app(self.temp.name)
        self.client = TestClient(self.app, headers=HEADERS)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temp.cleanup()

    def signup(self, username='researcher'):
        response = self.client.post('/api/auth/signup', json={'username':username,'password':'strong-password'})
        self.assertEqual(response.status_code, 201, response.text)
        return response

    def test_account_persistence_hashing_case_insensitive_login(self):
        response = self.signup()
        self.assertIn('HttpOnly', response.headers['set-cookie'])
        self.assertIn('SameSite=strict', response.headers['set-cookie'])
        with self.app.state.accounts.connect() as db:
            row = db.execute('SELECT * FROM users').fetchone()
            self.assertNotEqual(row['password_hash'], 'strong-password')
            self.assertTrue(row['password_hash'].startswith('scrypt$'))
        self.client.cookies.clear()
        self.assertEqual(self.client.get('/api/auth/me').status_code, 401)
        bad = self.client.post('/api/auth/login', json={'username':'researcher','password':'bad-password'})
        self.assertEqual(bad.status_code, 401)
        ok = self.client.post('/api/auth/login', json={'username':'RESEARCHER','password':'strong-password'})
        self.assertEqual(ok.status_code, 200)
        reopened = Accounts(self.temp.name)
        self.assertIsNotNone(reopened.login('researcher','strong-password'))

    def test_duplicate_username_and_validation(self):
        self.signup()
        duplicate = self.client.post('/api/auth/signup', json={'username':'RESEARCHER','password':'another-password'})
        self.assertEqual(duplicate.status_code, 409)
        weak = self.client.post('/api/auth/signup', json={'username':'name','password':'short'})
        self.assertEqual(weak.status_code, 422)
        invalid = self.client.post('/api/auth/signup', json={'username':"' OR 1=1 --",'password':'another-password'})
        self.assertEqual(invalid.status_code, 422)

    def test_expired_tampered_and_revoked_tokens_rejected(self):
        self.signup()
        token = self.client.cookies.get(COOKIE)
        claims = jwt.decode(token, self.app.state.accounts.secret, algorithms=['HS256'], audience='adf-web')
        claims['exp'] = int(time.time())-10
        expired = jwt.encode(claims, self.app.state.accounts.secret, algorithm='HS256')
        self.assertIsNone(self.app.state.accounts.user_from_token(expired))
        self.assertIsNone(self.app.state.accounts.user_from_token(token+'x'))
        self.assertEqual(self.client.post('/api/auth/logout').status_code, 204)
        self.assertIsNone(self.app.state.accounts.user_from_token(token))
        self.assertEqual(self.client.get('/api/auth/me').status_code, 401)

    def test_csrf_and_anonymous_document_access(self):
        blocked = self.client.post('/api/auth/signup', headers={'Origin':'https://untrusted.example'}, json={'username':'name','password':'strong-password'})
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(self.client.get('/api/reviews').status_code, 401)
        self.assertEqual(self.client.post('/api/reviews', content=sample_bytes()).status_code, 401)

    def test_netlify_origin_and_private_cache_headers(self):
        with patch.dict('os.environ', {'ADF_ALLOWED_ORIGINS': 'https://autodocu.netlify.app', 'ADF_SECURE_COOKIES': '1'}):
            response = self.client.post('/api/auth/signup', headers={'Origin': 'https://autodocu.netlify.app'}, json={'username': 'netlifyuser', 'password': 'strong-password'})
            self.assertEqual(response.status_code, 201, response.text)
            self.assertIn('Secure', response.headers['set-cookie'])
            self.assertEqual(response.headers['cache-control'], 'no-store')
            blocked = self.client.post('/api/auth/login', headers={'Origin': 'https://autodocu.netlify.app.evil.example'}, json={'username': 'netlifyuser', 'password': 'strong-password'})
            self.assertEqual(blocked.status_code, 403)

    def test_upload_download_and_cross_user_isolation(self):
        self.signup()
        response = self.client.post('/api/reviews', content=sample_bytes(), headers={'X-Filename':'research.docx'})
        self.assertEqual(response.status_code, 201, response.text)
        review = response.json()
        self.assertGreater(review['total'], 0)
        self.assertEqual(len(review['sections']), 9)
        self.assertEqual(self.client.get(f"/api/reviews/{review['id']}/download/corrected").status_code, 409)
        groups = ['fonts','sizes','spacing','margins','headers']
        plan = self.client.post(f"/api/reviews/{review['id']}/corrections/preview", json={'groups':groups}).json()
        approval = self.client.post(f"/api/reviews/{review['id']}/corrections/approve",
                                    json={'groups':groups,'preview_id':plan['preview_id'],'approved':True})
        self.assertEqual(approval.status_code, 200, approval.text)
        for kind, signature in [('pdf',b'%PDF'),('highlighted',b'PK'),('corrected',b'PK')]:
            download = self.client.get(f"/api/reviews/{review['id']}/download/{kind}")
            self.assertEqual(download.status_code, 200)
            self.assertTrue(download.content.startswith(signature))
        self.assertEqual(len(self.client.get('/api/reviews').json()), 1)
        self.client.post('/api/auth/logout')
        self.signup('other-user')
        self.assertEqual(self.client.get('/api/reviews').json(), [])
        self.assertEqual(self.client.get(f"/api/reviews/{review['id']}").status_code, 404)
        self.assertEqual(self.client.get(f"/api/reviews/{review['id']}/download/pdf").status_code, 404)

    def test_invalid_document_returns_useful_error(self):
        self.signup()
        response = self.client.post('/api/reviews', content=b'not a docx', headers={'X-Filename':'draft.docx'})
        self.assertEqual(response.status_code, 422)
        self.assertIn('valid Word', response.json()['detail'])

    def test_auth_rate_limit(self):
        for _ in range(15):
            response = self.client.post('/api/auth/login', json={'username':'unknown','password':'not-the-password'})
            self.assertEqual(response.status_code, 401)
        response = self.client.post('/api/auth/login', json={'username':'unknown','password':'not-the-password'})
        self.assertEqual(response.status_code, 429)


if __name__ == '__main__':
    unittest.main()
