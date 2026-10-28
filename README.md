# AI Video Source Finder (React + Django REST Framework)

Windows-friendly MVP for uploading a video, extracting representative frames, calculating perceptual hashes, and searching YouTube for candidate videos using the YouTube Data API.

## Important limitations
- This is a candidate-finding prototype, not a universal reverse-video search engine.
- The YouTube integration searches YouTube by text queries (currently based on the uploaded file name and optional user query). It does NOT search YouTube's entire video library by uploaded video pixels.
- Frame hashes can compare uploaded frames to frames that you separately obtain lawfully. The MVP stores extracted frame hashes, but does not automatically download arbitrary social-media videos.
- Instagram, Facebook, TikTok, and X do not provide a general public API that can search every post by an uploaded video. Platform access, permissions, indexing, and rate limits apply.
- Do not bypass login, access controls, robots restrictions, or platform terms.

## Requirements
- Python 3.11 or 3.12 recommended for a smoother Windows setup.
- Node.js LTS
- Optional YouTube Data API v3 key from Google Cloud Console.

## Backend setup (PowerShell)
```powershell
cd ai-video-source-finder
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
if (!(Test-Path backend\.env)) { Copy-Item backend\.env.example backend\.env }
python backend\manage.py migrate
python backend\manage.py runserver
```
If PowerShell blocks activation, run:
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

Edit `backend\.env` and set `YOUTUBE_API_KEY=your_key_here` if you have a key. The app still runs without it; YouTube search will return an informative message.

## Frontend setup (second terminal)
```powershell
cd ai-video-source-finder\frontend
npm install
npm run dev
```
Open the Vite URL printed in the terminal, usually http://localhost:5173.

Open `http://localhost:5173/login.html` to create an account or sign in. The page uses the updated supplied design. Accounts use Django's user model and server sessions; video search also enforces authentication on the backend. The Vite server proxies `/api`, `/accounts`, and `/auth` to Django so browser requests use one origin.

### Google sign-in

Google OAuth uses django-allauth. In Google Cloud Console, create an OAuth client of type **Web application**, configure the consent screen, and add this authorized redirect URI:

`http://localhost:5173/accounts/google/login/callback/`

Set these in `backend\.env` (the client secret stays on the backend):

```text
GOOGLE_CLIENT_ID=your-web-client-id
GOOGLE_CLIENT_SECRET=your-web-client-secret
FRONTEND_BASE_URL=http://localhost:5173
```

Add `http://localhost:5173` as an authorized JavaScript origin if Google Cloud requests one. Both Google buttons submit through the same allauth OAuth flow, which validates state and the provider response before creating/linking the Django user and session. A Google email must be verified before allauth can link it to an existing account. The backend currently detects both OAuth credentials; sign-in will work once the exact callback URI above is saved on the Google OAuth client and its consent screen allows your account.

For deployment, set `FRONTEND_BASE_URL` to the HTTPS application origin and route `/api/`, `/accounts/`, and `/auth/` to Django. Register that origin's `/accounts/google/login/callback/` as an authorized redirect URI. Keep `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE` enabled in production by setting `DJANGO_DEBUG=False`.

### Password reset email

Forgot password uses Django's reset-token workflow with a one-hour token lifetime. In local development, Django prints reset emails to the backend terminal. In production, set `DJANGO_DEBUG=False` and configure `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, and `DEFAULT_FROM_EMAIL` in `backend\.env`; do not commit those values. The reset page uses the same frontend origin and Django routes.

## API
- `GET /api/health/`
- `GET /api/auth/csrf/`
- `POST /api/auth/signup/` (`email`, `password`)
- `POST /api/auth/login/` (`email`, `password`, optional `remember`)
- `GET /api/auth/google/start/` (returns the OAuth start URL when configured)
- `POST /api/auth/logout/`
- `GET /api/auth/me/`
- Django password reset pages under `/auth/password_reset/`
- `POST /api/search/` multipart form fields:
  - `video`: video file (required)
  - `query`: optional text query
- `GET /api/jobs/<id>/`

## Free tier
- React, Django, DRF, django-allauth, OpenCV, imagehash, and Pillow: free/open source.
- YouTube Data API has a quota system; search.list typically costs 100 quota units per request under the standard quota allocation. Check current Google Cloud Console quota and terms.
- Local execution is free except electricity/storage. Public deployment, persistent media storage, and higher-volume APIs may cost money.
- API quota and results do not guarantee that the exact same video will be found.
