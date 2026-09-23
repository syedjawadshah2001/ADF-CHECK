# ADF Check 2.0 - Academic document review workspace

The primary app now uses **React + Vite**, a **FastAPI** document-processing API,
**SQLite** accounts and **JWT** authentication. Firebase is not required.

## First-time setup (PowerShell)

```powershell
cd "D:\ADF Check Implementation\utilities"
python -m pip install -r requirements.txt
cd frontend
npm.cmd install
npm.cmd run build
cd ..
python run.py
```

Open **http://127.0.0.1:8000**. Create an account with a username and password.
The username accepts 3-32 letters, numbers, dots, underscores or hyphens.
Passwords must contain 8-128 characters. Existing Firebase users must create a
local account: passwords cannot safely be copied from Firebase.

## Subsequent runs

```powershell
cd "D:\ADF Check Implementation\utilities"
python run.py
```

The Python server serves the built React frontend and API at the same address.
If ADF Check is already running, the launcher prints its address and exits cleanly.
If another application uses port 8000, run `python run.py --port 8001` and open
http://127.0.0.1:8001 instead.
No Firebase web key, Firebase service account, email, or cloud database is needed.
Node 22.12+ (or 20.19+) is needed for the frontend build. `npm.cmd` avoids
PowerShell execution-policy problems with `npm.ps1`.

## Frontend development

Use two terminals:

```powershell
# Terminal 1, in utilities
python -m uvicorn api:app --host 127.0.0.1 --port 8000 --reload
```

```powershell
# Terminal 2, in utilities/frontend
npm.cmd run dev
```

Open the URL printed by Vite (normally http://127.0.0.1:5173). Its `/api` proxy
connects to the Python server. Rebuild with `npm.cmd run build` before using
`python run.py` to see frontend changes.

## Account storage and security

- `data/accounts.sqlite3` stores usernames, salted scrypt password hashes, user
  IDs and a token version used to revoke sessions. It also stores up to 20 private
  formatting profiles per account. No raw passwords or documents are saved.
- Signed HS256 JWTs expire after one hour. JWTs are in HttpOnly, SameSite=Strict
  cookies, never localStorage. Logout invalidates all current JWTs for that user.
- Mutating API requests require an application header and validated request origin.
- Login/signup attempts are rate-limited. Queries use SQLite parameters.
- A random signing secret is created once in `data/jwt.key`. Keep this file and the
  database private. Both are ignored by Git. Back up the complete data directory
  while the server is stopped if you need to preserve accounts.
- Optional `ADF_JWT_SECRET` overrides the local key (minimum 32 characters).
  `ADF_DATA_DIR` overrides the data directory. Environment files are not loaded
  automatically; set environment variables in the shell.
- This setup binds to localhost. For deployment behind HTTPS, set
  `ADF_SECURE_COOKIES=1`, configure the intended origins and run a single API
  worker. Rate limits and temporary review storage are process-local.

The implementation follows FastAPI's JWT verification approach:
https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/

## Document workflow

Upload -> nine formatting checks -> review findings -> download PDF report,
highlighted DOCX -> preview selected correction categories -> explicitly approve -> download corrected DOCX. The original document is unchanged.

Results are kept only in bounded server memory: at most 10 per account for an
hour, subject to a shared 200 MB limit. They disappear after a server restart.
Downloads require the owning account's valid JWT. No documents or review history
are permanently stored in SQLite. Download important results before they expire.
Only two analyses run concurrently to keep the local app responsive. Uploads are
limited to 20 MB compressed and 100 MB expanded.

The built-in default profile uses Arial 12 pt body/headings, Arial 11 pt numbered
captions, Arial 9 pt headers/footers, one-inch margins and 1.5 line spacing.
Correction preserves text, tables and fields. References, heading hierarchy and
missing page-number fields still need manual review. Page locations are estimates;
APA checks are pattern based. Counts represent issue groups, not affected runs.

Optional AI estimates require `RAPIDAPI_KEY`. Users must opt in before the first
3,000 characters are sent to that external service. This is not plagiarism
verification or proof of authorship. All formatting checks work without that key.

## Tests

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -v
cd frontend
npm.cmd test
npm.cmd run build
```

API tests cover signup/login, hashed persistent passwords, duplicate usernames,
JWT expiry/tampering/logout, CSRF protection, rate limiting, document analysis,
all downloads and cross-user isolation. React tests cover forms, validation and
upload/results interactions. PDF tests check long content, counts and pagination.

The obsolete Streamlit/Firebase interface and unused Firebase credential file have
been removed. Keep `data/` (accounts and JWT signing key), `frontend/dist/` (the
built UI), and the active Python modules. `frontend/node_modules/` is needed for
frontend development/builds; `.pdf-tools/`, when present, supports PDF tests.


## Version 2 features

1. **Profiles:** Use University profiles to copy the ADF default, enter handbook
   rules, save a named department profile and select it before uploading. No
   institution-specific rules are invented or presented as certified. Saved
   profiles persist in SQLite; every review freezes its chosen rule values.
2. **Document assistant:** Local mode retrieves passages and explains detected
   findings with clickable paragraph references. It works without an API key but
   is a rule-based assistant, not generative AI. It supports questions about
   errors, paragraphs, matching phrases, correction steps and readiness. The last
   six exchanges stay in temporary review memory. Arbitrary reasoning requires
   the optional AI mode below.
3. **Preview & approve:** Select typefaces, sizes, spacing, margins and/or headers.
   Inspect actual before/after formatting-property values; previews show up to
   150 changes with full counts. This is not a Word page rendering. Changing a
   selection invalidates its approval token. Corrected downloads are locked until
   explicit approval. Only selected categories change; original content is kept.
4. **Submission plan:** A deterministic workflow combines selected rules,
   formatting findings and required-section heading detection into tasks. Users
   can acknowledge and export the checklist. Acknowledgement never removes a
   finding or certifies compliance. Approving corrections triggers a recheck of
   the generated copy and displays the number of remaining findings. Re-upload
   that copy for its full new report; the original review and PDF are retained.

Paragraph references use stable IDs within each review, including body and table
paragraphs. They are not page numbers. Unspecified/theme fonts, complex Word
features, reference accuracy, academic quality and final layout need human review.
AI never receives file-editing or submission tools.

### Optional AI interpretation

Set these in the terminal **before restarting the Python server**:

```powershell
$env:OPENAI_API_KEY = "your-key"
$env:ADF_AI_MODEL = "your-available-Responses-API-model"
python run.py
```

Choose a text model available to your OpenAI API account. No model or secret is
hard-coded. In Document assistant, enable AI and consent to sending selected
excerpts, the question, recent messages, rules and a bounded set of findings.
Provider charges may apply. Requests use `store=false`, a response output limit,
network timeouts, no tool access and paragraph-reference validation. AI mode does
not silently fall back to fabricated answers on provider failure. The server key
is never sent to the browser. Provider data handling still applies; `store=false`
is not a promise of zero provider retention.

API contract: https://developers.openai.com/api/reference/typescript/resources/responses/methods/create

The previously started plagiarism adapter is not part of the four version 2 UI
features. No live similarity checks or source verification are claimed by the
assistant. The separate AI-writing estimate is also not a plagiarism check.

### Upgrade / demo

Rebuild the frontend, stop the old Python server with Ctrl+C, then run
`python run.py`. Existing usernames/passwords remain valid. Reviews, excerpts and
chat are temporary and disappear on restart; saved accounts and profiles remain.
For a demo: create profile -> upload draft -> ask about P2 -> preview only margins
-> approve -> inspect remaining findings -> export submission checklist.

Validation includes selective correction, content preservation, profile snapshots,
private ownership of every new API route, approval-token mismatch, consent gating,
local chat without network calls and rejection of invented AI paragraph IDs.
Live OpenAI responses require your credentials and were not exercised by offline tests.
