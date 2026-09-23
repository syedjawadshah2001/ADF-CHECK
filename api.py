"""React application API. Run with: python -m uvicorn api:app --host 127.0.0.1."""
import logging
import os
import sqlite3
import sys
import threading
import time
import uuid
import json
from io import BytesIO
from docx import Document
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from utilities.local_auth import Accounts, SESSION_SECONDS
from utilities.analysis_service import analyze, MAX_UPLOAD_BYTES
from utilities.report import _parse_sections, count_issues
from utilities import plagiarism
from utilities.formatting import iter_paragraphs
from utilities.profiles import FormattingProfile, DEFAULT_PROFILE, CORRECTION_GROUPS
from utilities.corrections import preview as correction_preview
from utilities.review_engine import inspect_document, readiness
from utilities import document_assistant
from typing import Literal

ROOT = Path(__file__).resolve().parent
COOKIE = 'adf_session'


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r'^[a-zA-Z0-9_.-]+$')
    password: str = Field(min_length=8, max_length=128)


class ScanConsent(BaseModel):
    consent: bool


class CorrectionRequest(BaseModel):
    groups: list[Literal['fonts', 'sizes', 'spacing', 'margins', 'headers']] = Field(min_length=1, max_length=5)


class CorrectionApproval(CorrectionRequest):
    preview_id: str = Field(min_length=64, max_length=64)
    approved: bool


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    use_ai: bool = False
    consent: bool = False


class TaskAcknowledgement(BaseModel):
    task_id: str = Field(min_length=1, max_length=120)
    checked: bool


class ResultStore:
    """Bounded in-memory results, expiring after an hour; no documents in SQLite."""
    def __init__(self):
        self.items = {}
        self.lock = threading.Lock()

    def prune(self):
        now = time.time()
        for key in list(self.items):
            if self.items[key]['expires'] < now:
                del self.items[key]

    def put(self, owner, filename, result):
        with self.lock:
            self.prune()
            user_keys = [k for k,v in self.items.items() if v['owner'] == owner]
            while len(user_keys) >= 10:
                del self.items[user_keys.pop(0)]
            size = sum(len(result.get(k) or b'') for k in ('pdf','highlighted','corrected','original'))
            size += len(json.dumps({k:result[k] for k in ('paragraphs','findings','profile','readiness')}).encode())
            while self.items and sum(v['size'] for v in self.items.values()) + size > 200*1024*1024:
                del self.items[next(iter(self.items))]
            if size > 200*1024*1024:
                raise ValueError('The generated downloads are too large. Please use a smaller document.')
            key = uuid.uuid4().hex
            sections = _parse_sections(result['errors'])
            summary = {k: count_issues(v) for k,v in sections.items()}
            public = {'id': key, 'filename': filename, 'created_at': datetime.now(timezone.utc).isoformat(),
                      'expires_at': datetime.fromtimestamp(time.time()+SESSION_SECONDS, timezone.utc).isoformat(),
                      'sections': sections, 'summary': summary, 'total': sum(summary.values()),
                      'words': result['words'], 'ai': result['ai'], 'plagiarism': {'status': 'not_started'},
                      'profile': result['profile'], 'findings': result['findings'], 'paragraph_count': len(result['paragraphs']),
                      'readiness': result['readiness'], 'approval': None, 'acknowledged_tasks': [], 'assistant_history': []}
            self.items[key] = {'owner': owner, 'public': public, 'result': result, 'size': size, 'expires': time.time()+SESSION_SECONDS,
                               'scan_lock': threading.Lock(), 'scan_id': None, 'next_poll': 0,
                               'work_lock': threading.Lock(), 'chat_attempts': deque()}
            return public

    def get(self, key, owner):
        with self.lock:
            self.prune()
            item = self.items.get(key)
            if not item or item['owner'] != owner:
                raise HTTPException(404, 'This review has expired or is unavailable. Analyze the document again.')
            return item

    def history(self, owner):
        with self.lock:
            self.prune()
            return [v['public'] for v in reversed(list(self.items.values())) if v['owner'] == owner]


def create_app(data_directory=None):
    @asynccontextmanager
    async def lifespan(application):
        application.state.accounts = Accounts(data_directory or os.environ.get('ADF_DATA_DIR', str(ROOT/'data')))
        yield

    app = FastAPI(title='ADF Check API', lifespan=lifespan)
    store = ResultStore()
    slots = threading.BoundedSemaphore(2)
    attempts = defaultdict(deque)
    attempts_lock = threading.Lock()

    @app.middleware('http')
    async def security(request, call_next):
        if request.url.path.startswith('/api/') and request.method not in ('GET','HEAD','OPTIONS'):
            origin = request.headers.get('origin')
            allowed = {str(request.base_url).rstrip('/'), 'http://127.0.0.1:5173', 'http://localhost:5173'}
            if request.headers.get('x-requested-with') != 'ADF-Web' or (origin and origin not in allowed):
                from fastapi.responses import JSONResponse
                return JSONResponse({'detail':'Request origin could not be verified.'}, status_code=403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['X-Frame-Options'] = 'DENY'
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    def account(request: Request):
        user = request.app.state.accounts.user_from_token(request.cookies.get(COOKIE, ''))
        if not user:
            raise HTTPException(401, 'Please sign in to continue. Your session may have expired.')
        return user

    def limit(request):
        key = request.client.host if request.client else 'local'
        now = time.monotonic()
        with attempts_lock:
            for address in list(attempts):
                while attempts[address] and attempts[address][0] < now-60:
                    attempts[address].popleft()
                if not attempts[address]:
                    del attempts[address]
            if len(attempts[key]) >= 15:
                raise HTTPException(429, 'Too many account attempts. Please wait one minute.', headers={'Retry-After':'60'})
            attempts[key].append(now)

    def session(response, request, user):
        response.set_cookie(COOKIE, request.app.state.accounts.token(user), httponly=True,
                            secure=os.environ.get('ADF_SECURE_COOKIES') == '1', samesite='strict',
                            max_age=SESSION_SECONDS, path='/api')
        return {'id':user['id'], 'username':user['username']}

    @app.get('/api/health')
    def health():
        return {'status':'ok', 'version':'2.0'}

    def resolve_profile(request, profile_id, owner):
        if profile_id == 'default':
            return DEFAULT_PROFILE.model_dump()
        with request.app.state.accounts.connect() as db:
            row = db.execute('SELECT rules FROM formatting_profiles WHERE id=? AND owner=?', (profile_id, owner)).fetchone()
        if not row:
            raise HTTPException(404, 'Formatting profile not found.')
        return FormattingProfile.model_validate_json(row['rules']).model_dump()

    @app.get('/api/profiles')
    def profiles(request: Request, user=Depends(account)):
        with request.app.state.accounts.connect() as db:
            rows = db.execute('SELECT id,rules FROM formatting_profiles WHERE owner=? ORDER BY rowid DESC', (user['id'],)).fetchall()
        return [{'id':'default', 'rules':DEFAULT_PROFILE.model_dump(), 'builtin':True}] + [
            {'id':r['id'], 'rules':json.loads(r['rules']), 'builtin':False} for r in rows]

    @app.post('/api/profiles', status_code=201)
    def save_profile(body: FormattingProfile, request: Request, user=Depends(account)):
        key = uuid.uuid4().hex
        with request.app.state.accounts.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT COUNT(*) FROM formatting_profiles WHERE owner=?', (user['id'],)).fetchone()[0] >= 20:
                raise HTTPException(409, 'You can save up to 20 profiles. Delete an unused profile first.')
            db.execute('INSERT INTO formatting_profiles(id,owner,rules) VALUES (?,?,?)', (key,user['id'],body.model_dump_json()))
        return {'id':key,'rules':body.model_dump(),'builtin':False}

    @app.delete('/api/profiles/{profile_id}', status_code=204)
    def delete_profile(profile_id: str, request: Request, user=Depends(account)):
        with request.app.state.accounts.connect() as db:
            if db.execute('DELETE FROM formatting_profiles WHERE id=? AND owner=?', (profile_id,user['id'])).rowcount == 0:
                raise HTTPException(404, 'Profile not found or is the built-in default.')

    @app.get('/api/assistant/config')
    def assistant_config(user=Depends(account)):
        return {'ai_enabled':document_assistant.ai_available(), 'local_enabled':True,
                'provider':'OpenAI', 'note':'AI is optional. Local answers use document passages and rule-based findings.'}

    @app.post('/api/auth/signup', status_code=201)
    def signup(body: Credentials, request: Request, response: Response):
        limit(request)
        try:
            user = request.app.state.accounts.signup(body.username, body.password)
        except sqlite3.IntegrityError:
            raise HTTPException(409, 'That username is already taken. Try another or sign in.')
        return session(response, request, user)

    @app.post('/api/auth/login')
    def login(body: Credentials, request: Request, response: Response):
        limit(request)
        user = request.app.state.accounts.login(body.username, body.password)
        if not user:
            raise HTTPException(401, 'Incorrect username or password.')
        return session(response, request, user)

    @app.get('/api/auth/me')
    def me(user=Depends(account)):
        return user

    @app.post('/api/auth/logout', status_code=204)
    def logout(request: Request, response: Response, user=Depends(account)):
        request.app.state.accounts.revoke(user['id'])
        response.delete_cookie(COOKIE, path='/api')

    @app.get('/api/reviews')
    def history(user=Depends(account)):
        return store.history(user['id'])

    @app.get('/api/reviews/{review_id}')
    def review(review_id: str, user=Depends(account)):
        return store.get(review_id, user['id'])['public']

    @app.get('/api/reviews/{review_id}/paragraphs/{paragraph_id}')
    def paragraph(review_id: str, paragraph_id: str, user=Depends(account)):
        item = store.get(review_id, user['id'])
        row = next((p for p in item['result']['paragraphs'] if p['id'] == paragraph_id), None)
        if not row:
            raise HTTPException(404, 'Paragraph not found.')
        return {**row, 'findings':[f for f in item['result']['findings'] if f['location']==paragraph_id]}

    @app.post('/api/reviews/{review_id}/corrections/preview')
    def preview_corrections(review_id: str, body: CorrectionRequest, user=Depends(account)):
        item = store.get(review_id, user['id'])
        if not slots.acquire(blocking=False):
            raise HTTPException(429, 'Document processing is busy. Try again shortly.')
        try:
            result, _ = correction_preview(item['result']['original'], item['result']['profile'], body.groups)
            return result
        finally:
            slots.release()

    @app.post('/api/reviews/{review_id}/corrections/approve')
    def approve_corrections(review_id: str, body: CorrectionApproval, user=Depends(account)):
        item = store.get(review_id, user['id'])
        if not body.approved:
            raise HTTPException(422, 'Approve the preview before generating a corrected document.')
        if not slots.acquire(blocking=False):
            raise HTTPException(429, 'Document processing is busy. Try again shortly.')
        try:
            with item['work_lock']:
                plan, corrected = correction_preview(item['result']['original'], item['result']['profile'], body.groups)
                if plan['preview_id'] != body.preview_id:
                    raise HTTPException(409, 'The selection changed. Generate and approve a new preview.')
                checked = inspect_document(Document(BytesIO(corrected)), item['result']['profile'])
                approval = {'groups':plan['groups'], 'total_changes':plan['total_changes'],
                            'remaining_findings':len(checked['findings']), 'readiness':readiness(checked),
                            'approved_at':datetime.now(timezone.utc).isoformat()}
                with store.lock:
                    new_size = item['size'] - len(item['result'].get('corrected') or b'') + len(corrected)
                    if sum(v['size'] for v in store.items.values())-item['size']+new_size > 200*1024*1024:
                        raise HTTPException(409, 'Temporary storage is full. Try again after older reviews expire.')
                    item['size'] = new_size
                    item['result']['corrected'] = corrected
                    item['public']['approval'] = approval
                return approval
        finally:
            slots.release()

    @app.post('/api/reviews/{review_id}/readiness/acknowledge')
    def acknowledge_task(review_id: str, body: TaskAcknowledgement, user=Depends(account)):
        item = store.get(review_id, user['id'])
        with item['work_lock']:
            allowed = {t['id'] for t in item['public']['readiness']['tasks']}
            if body.task_id not in allowed:
                raise HTTPException(404, 'Checklist task not found.')
            current = set(item['public']['acknowledged_tasks'])
            current.add(body.task_id) if body.checked else current.discard(body.task_id)
            item['public']['acknowledged_tasks'] = sorted(current)
            return {'acknowledged_tasks':sorted(current)}

    @app.post('/api/reviews/{review_id}/assistant')
    def ask_assistant(review_id: str, body: ChatRequest, user=Depends(account)):
        item = store.get(review_id, user['id'])
        if not body.question.strip():
            raise HTTPException(422, 'Enter a question.')
        if body.use_ai and not body.consent:
            raise HTTPException(422, 'Consent is required to send excerpts and recent messages to OpenAI.')
        if not item['work_lock'].acquire(blocking=False):
            raise HTTPException(409, 'A request for this document is already running.')
        try:
            now = time.monotonic()
            while item['chat_attempts'] and item['chat_attempts'][0] < now-60:
                item['chat_attempts'].popleft()
            if len(item['chat_attempts']) >= 10:
                raise HTTPException(429, 'Please wait a minute before asking more questions.')
            item['chat_attempts'].append(now)
            history = item['public']['assistant_history']
            try:
                answer = document_assistant.ai_answer(item['result'], body.question, history) if body.use_ai else document_assistant.local_answer(item['result'], body.question)
            except ValueError as exc:
                raise HTTPException(503, str(exc))
            history.extend([{'role':'user','text':body.question}, {'role':'assistant',**answer}])
            del history[:-12]
            return answer
        finally:
            item['work_lock'].release()

    @app.get('/api/plagiarism/config')
    def plagiarism_config(user=Depends(account)):
        return {'enabled': plagiarism.configured(), 'provider': plagiarism.PROVIDER,
                'language': 'English', 'max_characters': plagiarism.MAX_CHARACTERS}

    @app.post('/api/reviews/{review_id}/plagiarism')
    def start_plagiarism(review_id: str, body: ScanConsent, user=Depends(account)):
        item = store.get(review_id, user['id'])
        if not body.consent:
            raise HTTPException(422, 'Consent is required before sending text to the external plagiarism service.')
        if not plagiarism.configured():
            raise HTTPException(503, 'Set PLAGIARISMCHECK_API_TOKEN on the server to enable plagiarism checks.')
        if not item['scan_lock'].acquire(blocking=False):
            raise HTTPException(409, 'A scan request is already in progress.')
        try:
            if item['public']['plagiarism']['status'] != 'not_started':
                return item['public']['plagiarism']
            text = '\n'.join(p.text for p in iter_paragraphs(Document(BytesIO(item['result']['highlighted']))) if p.text.strip())
            if not 80 <= len(text.strip()) <= plagiarism.MAX_CHARACTERS:
                raise HTTPException(422, 'This scan requires 80–100,000 characters of extracted text. No text was sent.')
            item['public']['plagiarism'] = {'status': 'submitting', 'provider': plagiarism.PROVIDER}
            try:
                item['scan_id'] = plagiarism.submit(text)
            except plagiarism.PlagiarismError as exc:
                # Never automatically resubmit a potentially billed POST after a timeout.
                item['public']['plagiarism'] = {'status': 'failed', 'provider': plagiarism.PROVIDER, 'message': str(exc)}
                return item['public']['plagiarism']
            item['public']['plagiarism'] = {'status': 'pending', 'provider': plagiarism.PROVIDER}
            item['next_poll'] = time.monotonic() + 5
            return item['public']['plagiarism']
        finally:
            item['scan_lock'].release()

    @app.get('/api/reviews/{review_id}/plagiarism')
    def plagiarism_result(review_id: str, user=Depends(account)):
        item = store.get(review_id, user['id'])
        if not item['scan_lock'].acquire(blocking=False):
            return item['public']['plagiarism']
        try:
            if item['public']['plagiarism']['status'] != 'pending' or time.monotonic() < item['next_poll']:
                return item['public']['plagiarism']
            item['next_poll'] = time.monotonic() + 10
            try:
                item['public']['plagiarism'] = plagiarism.status(item['scan_id'])
            except plagiarism.PlagiarismError as exc:
                item['public']['plagiarism'] = {'status': 'pending', 'provider': plagiarism.PROVIDER, 'message': str(exc)}
            return item['public']['plagiarism']
        finally:
            item['scan_lock'].release()

    @app.post('/api/reviews', status_code=201)
    async def upload(request: Request, include_ai: bool=False, profile_id: str='default', user=Depends(account)):
        selected_profile = resolve_profile(request, profile_id, user['id'])
        filename = unquote(request.headers.get('x-filename','document.docx')).replace('\\', '/').split('/')[-1][:180]
        if not filename.lower().endswith('.docx'):
            raise HTTPException(422, 'Choose a Word .docx document.')
        if not slots.acquire(blocking=False):
            raise HTTPException(429, 'Other documents are being checked. Please try again shortly.')
        try:
            content = bytearray()
            async for chunk in request.stream():
                content.extend(chunk)
                if len(content) > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, 'Documents must be smaller than 20 MB.')
            result = await run_in_threadpool(analyze, bytes(content), include_ai, selected_profile=selected_profile, generate_correction=False)
            return store.put(user['id'], filename, result)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        except HTTPException:
            raise
        except Exception:
            logging.getLogger(__name__).exception('Document analysis failed')
            raise HTTPException(422, 'Unable to read this document. Save it as a valid .docx file and try again.')
        finally:
            slots.release()

    @app.get('/api/reviews/{review_id}/download/{kind}')
    def download(review_id: str, kind: str, user=Depends(account)):
        if kind == 'similarity':
            result = store.get(review_id, user['id'])['public']['plagiarism']
            if result['status'] != 'completed':
                raise HTTPException(409, 'The similarity report is not ready.')
            return Response(json.dumps(result, ensure_ascii=False), media_type='application/json',
                            headers={'Content-Disposition': 'attachment; filename="similarity_report.json"'})
        if kind not in ('pdf', 'highlighted', 'corrected'):
            raise HTTPException(404, 'Download not found.')
        item = store.get(review_id, user['id'])
        if kind == 'corrected' and not item['public']['approval']:
            raise HTTPException(409, 'Preview and approve corrections before downloading the corrected document.')
        mime = 'application/pdf' if kind == 'pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        filename = 'ADF_Validation_Report.pdf' if kind == 'pdf' else f'{kind}_document.docx'
        return Response(item['result'][kind], media_type=mime, headers={'Content-Disposition':f'attachment; filename="{filename}"'})

    build = ROOT/'frontend'/'dist'
    if build.exists():
        app.mount('/assets', StaticFiles(directory=build/'assets'), name='assets')

        @app.get('/')
        def frontend():
            return FileResponse(build/'index.html')

    return app


app = create_app()
